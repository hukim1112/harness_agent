"""
app/evaluate/runner.py
======================
`main_agent` 중심 오프라인 배치 평가 러너 (노트북 4 & CLI 공용)

골든 데이터셋으로 `main_agent` 하네스를 실행하고, 기본 제공 메트릭 또는 사용자가 조합한
커스텀 메트릭 리스트(`metrics=[...]`)로 채점한 뒤 실패 계층 진단, 전후 비교(`compare_table`),
다중 시행 신뢰도(`pass@k` / `pass^k`), CI 회귀 게이트를 수행합니다.

사용 예:
  python -m app.evaluate.runner
  python -m app.evaluate.runner --ids data-01 err-01 neg-01
  python -m app.evaluate.runner --trials 3 --ids calc-01 err-01
  python -m app.evaluate.runner --compare artifacts/eval_runs/main_agent_baseline.json --fail-on-regression
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Sequence
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from app.context import AgentContext
from app.evaluate.metrics import EvalMetric, EvalSample, PRESET_METRICS
from app.evaluate.schemas import HarnessJudge
from app.middleware.error_control.self_correction import StopHooksMiddleware
from app.middleware.error_control.self_recovery import (
    ModelCallLimitMiddleware,
    ToolErrorHandlerMiddleware,
)
from app.middleware.evaluator.evaluator import (
    DEFAULT_JUDGE_MODEL,
    extract_last_ai_answer,
    extract_tool_contexts,
)
from app.middleware.prompt import (
    PromptAssembler,
    SkillPromptBuilder,
    create_prompt_assembler_middleware,
)
from app.tools.plan import plan_session_scope
from app.utils import init_chat_model

GOLDEN_PATH = os.path.join(PROJECT_ROOT, "data/eval/golden_eval_dataset.json")
REPORT_DIR = os.path.join(PROJECT_ROOT, "artifacts/eval_runs")
PASS_THRESHOLD = 0.75
NOISE_BAND = 0.10
JUDGE_MODEL = DEFAULT_JUDGE_MODEL
RECURSION_LIMIT = 40
NO_ANSWER = "(호출 한도 초과로 최종 답변을 생성하지 못함)"
JUDGE_PREVIEW_CHARS = 1500

_SUBAGENT_TOOL_NAMES = frozenset({
    "list_sub_agents",
    "invoke_sub_agent",
    "get_sub_agent_job_status",
    "cancel_sub_agent_job",
})
_WEB_TOOL_NAMES = frozenset({"web_search", "web_fetch"})


def load_golden(path: str = GOLDEN_PATH, ids: Optional[List[str]] = None) -> List[dict]:
    """골든 평가 데이터셋 JSON을 로드합니다."""
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    return [c for c in cases if not ids or c["id"] in ids]


def preview_for_judge(text: str, limit: int = JUDGE_PREVIEW_CHARS) -> str:
    """도구 결과를 과정 채점기용 발췌 문자열로 정리합니다."""
    cleaned = "\n".join(line for line in str(text).splitlines() if line.strip()).strip()
    return cleaned if len(cleaned) <= limit else cleaned[:limit] + " …(이하 생략)"


def trajectory_from_messages(messages: Sequence[Any]) -> List[Dict[str, Any]]:
    """AIMessage의 tool_calls와 ToolMessage 결과를 짝지어 도구 호출 궤적을 만듭니다."""
    results: Dict[str, Tuple[str, str]] = {}
    for m in messages:
        if isinstance(m, ToolMessage) or getattr(m, "type", None) == "tool":
            tc_id = getattr(m, "tool_call_id", None)
            if tc_id:
                status = getattr(m, "status", None) or "ok"
                results[tc_id] = (str(getattr(m, "content", "")), str(status))

    trajectory: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, AIMessage) or getattr(m, "type", None) == "ai":
            for tc in getattr(m, "tool_calls", None) or []:
                raw, status = results.get(tc.get("id", ""), ("", "ok"))
                trajectory.append({
                    "tool_name": tc.get("name", "unknown_tool"),
                    "arguments": tc.get("args", {}),
                    "status": status,
                    "response_snippet": raw[:200],
                    "result_preview": preview_for_judge(raw),
                })
    return trajectory


def _extract_token_totals(messages: Sequence[Any]) -> Tuple[int, int]:
    in_tok = 0
    out_tok = 0
    for m in messages:
        if not (isinstance(m, AIMessage) or getattr(m, "type", None) == "ai"):
            continue
        usage = getattr(m, "usage_metadata", None) or {}
        if not usage and hasattr(m, "response_metadata"):
            usage = (m.response_metadata or {}).get("token_usage", {}) or {}
        in_tok += int(usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0) or 0)
        out_tok += int(usage.get("output_tokens", 0) or usage.get("completion_tokens", 0) or 0)
    return in_tok, out_tok


def build_main_agent_for_eval(
    *,
    model: Optional[Any] = None,
    model_name: str = "gemini-3.8-flash",
    system_prompt: Optional[str] = None,
    tool_overrides: Optional[Dict[str, Any]] = None,
    include_subagent_tools: bool = False,
    include_web_tools: bool = False,
    include_custom_tools: bool = False,
    include_stop_hooks: bool = True,
    pre_middleware: Optional[Sequence[Any]] = None,
    extra_middleware: Optional[Sequence[Any]] = None,
    checkpointer: Optional[Any] = None,
    run_limit: int = 30,
):
    """`main`과 `instructor` 양쪽에서 동일하게 동작하는 평가 전용 `main_agent` 하네스를 조립합니다.

    - `main_agent/prompt.py`의 SUPERVISOR_SYSTEM_PROMPT와 `main_agent/skills/`를 그대로 사용합니다.
    - 오프라인 벤치마크의 결정성과 속도를 위해 HTTP 서버가 필요한 서브에이전트 도구 및
      외부 웹 도구는 기본 비활성화되며 필요 시 인자로 켤 수 있습니다.
    - Mission 01 커스텀 도구(`roll_dice` 등)는 `main`/`instructor` 간 동일한 11개 코어 도구를
      보장하고 Gemini 정수 `enum` 스키마 충돌을 피하기 위해 기본 제외(`include_custom_tools=False`)됩니다.
      필요 시 `include_custom_tools=True`로 명시적으로 포함할 수 있습니다.
    - `tool_overrides={"file_read": file_read_v2}`처럼 특정 도구만 교체해 전후 개선 실험을 수행할 수 있습니다.
    """
    from app.agents.main_agent.prompt import SUPERVISOR_SYSTEM_PROMPT
    from app.agents.main_agent.tools import tools_supervisor

    llm = model or init_chat_model(model=model_name, temperature=0.0)

    excluded: set[str] = set()
    if not include_subagent_tools:
        excluded.update(_SUBAGENT_TOOL_NAMES)
    if not include_web_tools:
        excluded.update(_WEB_TOOL_NAMES)

    active_tools: List[Any] = [
        t for t in tools_supervisor if getattr(t, "name", "") not in excluded
    ]

    if include_custom_tools:
        try:
            from app.tools import custom_tools as ct_mod

            seen_names = {getattr(t, "name", "") for t in active_tools}
            custom_candidates = list(getattr(ct_mod, "CUSTOM_TOOLS", []) or [])
            dice_fn = getattr(ct_mod, "roll_dice", None)
            if dice_fn is not None:
                custom_candidates.append(dice_fn)
            for fn in custom_candidates:
                fn_name = getattr(fn, "name", "")
                if fn is not None and fn_name not in seen_names:
                    active_tools.append(fn)
                    seen_names.add(fn_name)
        except Exception:
            pass

    if tool_overrides:
        replaced: List[Any] = []
        used_keys: set[str] = set()
        for t in active_tools:
            tname = getattr(t, "name", "")
            if tname in tool_overrides:
                replaced.append(tool_overrides[tname])
                used_keys.add(tname)
            else:
                replaced.append(t)
        for k, v in tool_overrides.items():
            if k not in used_keys:
                replaced.append(v)
        active_tools = replaced

    skills_dir = Path(PROJECT_ROOT) / "app" / "agents" / "main_agent" / "skills"
    guidelines = str(skills_dir / "SKILL.md") if (skills_dir / "SKILL.md").exists() else None
    skill_builder = SkillPromptBuilder(
        skills_dirs=[str(skills_dir)] if skills_dir.exists() else [],
        guidelines_path=guidelines,
    )
    assembler = PromptAssembler(
        system_prompt=(system_prompt or SUPERVISOR_SYSTEM_PROMPT),
        skill_guidelines=skill_builder.load_guidelines if guidelines else None,
        skill_provider=skill_builder.list_skills if skills_dir.exists() else None,
    )
    prompt_mw = create_prompt_assembler_middleware(assembler)

    middleware: List[Any] = list(pre_middleware or [])
    middleware.extend([
        prompt_mw,
        ToolErrorHandlerMiddleware(max_retries=0),
        ModelCallLimitMiddleware(run_limit=run_limit, exit_behavior="end"),
    ])
    if include_stop_hooks:
        middleware.append(StopHooksMiddleware())
    if extra_middleware:
        middleware.extend(extra_middleware)

    return create_agent(
        model=llm,
        tools=active_tools,
        middleware=middleware,
        checkpointer=checkpointer or InMemorySaver(),
        context_schema=AgentContext,
    )


async def load_app_agent(name: str):
    """app/agents/<name> 패키지의 팩토리로 서비스용 에이전트를 만듭니다."""
    module = importlib.import_module(f"app.agents.{name}")
    return await module.create_agent_executor()


async def run_case(
    agent: Any,
    case: dict,
    sandbox_root: Optional[str] = None,
) -> dict:
    """단일 평가 문항에 대해 에이전트를 격리 실행하고 궤적·답변·토큰·산출물 경로를 수집합니다."""
    started = time.time()
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
    base_sandbox = sandbox_root or os.path.join(PROJECT_ROOT, "artifacts", "eval_sandbox")
    artifact_dir = os.path.join(base_sandbox, thread_id)
    os.makedirs(artifact_dir, exist_ok=True)

    try:
        rel_artifact_dir = os.path.relpath(artifact_dir, PROJECT_ROOT).replace("\\", "/")
    except ValueError:
        rel_artifact_dir = artifact_dir.replace("\\", "/")

    question = str(case["question"]).replace("{output_dir}", rel_artifact_dir)
    expected_artifact = str(case.get("expected_artifact") or "").replace("{output_dir}", rel_artifact_dir)

    config: Dict[str, Any] = {
        "configurable": {"thread_id": thread_id, "user_id": "eval_runner"},
        "recursion_limit": RECURSION_LIMIT,
    }
    context = AgentContext(
        agent_name="main_agent",
        session_id=thread_id,
        user_id="eval_runner",
        workspace_dir=rel_artifact_dir,
    )

    hit_limit = False
    messages: List[Any] = []
    try:
        with plan_session_scope(thread_id, user_id="eval_runner"):
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=question)]},
                config=config,
                context=context,
            )
        messages = list(result.get("messages") or [])
    except GraphRecursionError:
        hit_limit = True
        try:
            state = await agent.aget_state(config)
            messages = list((state.values or {}).get("messages", []))
        except Exception:
            messages = []
    finally:
        # plan.py가 artifacts/users/eval_runner/sessions/{thread_id}에 생성한 임시 계획 보드 정리
        eval_user_session = Path(PROJECT_ROOT) / "artifacts" / "users" / "eval_runner" / "sessions" / thread_id
        shutil.rmtree(eval_user_session, ignore_errors=True)

    in_tok, out_tok = _extract_token_totals(messages)
    return {
        "question": question,
        "trajectory": trajectory_from_messages(messages),
        "answer": NO_ANSWER if hit_limit else extract_last_ai_answer(messages),
        "contexts": extract_tool_contexts(messages),
        "duration_s": round(time.time() - started, 1),
        "hit_limit": hit_limit,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "artifact_dir": rel_artifact_dir,
        "expected_artifact": expected_artifact,
    }


async def score_case_with_metrics(
    case: dict,
    record: dict,
    metrics: Sequence[EvalMetric],
    judge_llm: Any,
    judge: HarnessJudge,
) -> dict:
    """사용자가 조합한 메트릭 리스트(기본 + 커스텀)로 단일 문항을 채점합니다."""
    sample = EvalSample(
        id=case["id"],
        category=case["category"],
        question=record.get("question") or case["question"],
        ground_truth=case.get("ground_truth", ""),
        target_tools=case.get("target_tools", []),
        answer=record["answer"],
        contexts=record["contexts"],
        trajectory=record["trajectory"],
        duration_s=record["duration_s"],
        hit_limit=record.get("hit_limit", False),
        input_tokens=record.get("input_tokens", 0),
        output_tokens=record.get("output_tokens", 0),
        artifact_dir=record.get("artifact_dir", ""),
        expected_artifact=record.get("expected_artifact", ""),
        metadata=case.get("metadata") or {},
    )

    evaluated = await asyncio.gather(
        *(m.aevaluate(sample, judge_llm=judge_llm, judge=judge) for m in metrics)
    )

    metric_scores: Dict[str, float] = {}
    diagnoses: List[str] = []
    weighted_sum = 0.0
    total_weight = sum(m.weight for m in metrics if m.weight > 0)

    for m, (score, _) in zip(metrics, evaluated):
        metric_scores[m.name] = score
        if total_weight > 0:
            if m.weight > 0:
                weighted_sum += m.weight * score
        else:
            weighted_sum += score
        if m.threshold is not None and score < m.threshold:
            diagnoses.append(m.diagnosis)

    if record.get("hit_limit"):
        diagnoses.append("호출 한도 초과")

    denom = total_weight if total_weight > 0 else max(len(metrics), 1)
    composite = round(weighted_sum / denom, 3)

    traj_cached = sample._cache.get("trajectory_eval")
    out_cached = sample._cache.get("outcome_eval")

    row: Dict[str, Any] = {
        "id": case["id"],
        "category": case["category"],
        "composite": composite,
        "passed": composite >= PASS_THRESHOLD,
        **metric_scores,
        "tool_calls": len(record["trajectory"]),
        "tools": [t["tool_name"] for t in record["trajectory"]],
        "input_tokens": record.get("input_tokens", 0),
        "output_tokens": record.get("output_tokens", 0),
        "total_tokens": record.get("total_tokens", 0),
        "duration_s": record["duration_s"],
        "diagnoses": diagnoses,
        "critique": traj_cached.critique if traj_cached else "",
        "outcome_rationale": out_cached.rationale if out_cached else "",
        "question": sample.question,
        "answer": record["answer"],
        "metric_specs": [m.to_spec() for m in metrics],
    }
    if traj_cached is not None and "trajectory" not in row:
        row["trajectory"] = round(traj_cached.trajectory_score, 2)
    if out_cached is not None and "outcome" not in row:
        row["outcome"] = round(out_cached.outcome_score, 2)
    return row


def _aggregate_trial_rows(case: dict, trial_rows: List[dict], metrics: Sequence[EvalMetric]) -> dict:
    """동일 문항의 k회 반복 실행 결과를 집계해 pass@k / pass^k 및 평균 메트릭을 계산합니다."""
    if len(trial_rows) == 1:
        row = dict(trial_rows[0])
        row["trials"] = 1
        row["pass_at_k"] = 1.0 if row["passed"] else 0.0
        row["pass_pow_k"] = 1.0 if row["passed"] else 0.0
        row["pass_rate"] = 1.0 if row["passed"] else 0.0
        return row

    k = len(trial_rows)
    pass_flags = [bool(r["passed"]) for r in trial_rows]
    mean_of = lambda key: sum(float(r.get(key, 0.0)) for r in trial_rows) / k

    agg: Dict[str, Any] = {
        "id": case["id"],
        "category": case["category"],
        "composite": round(mean_of("composite"), 3),
        "passed": all(pass_flags),
        "trials": k,
        "pass_rate": round(sum(pass_flags) / k, 2),
        "pass_at_k": 1.0 if any(pass_flags) else 0.0,
        "pass_pow_k": 1.0 if all(pass_flags) else 0.0,
    }
    for m in metrics:
        agg[m.name] = round(mean_of(m.name), 2)

    all_diags: List[str] = []
    for r in trial_rows:
        for d in r.get("diagnoses") or []:
            if d not in all_diags:
                all_diags.append(d)

    rep = min(trial_rows, key=lambda r: r["composite"])
    agg.update({
        "tool_calls": round(mean_of("tool_calls"), 1),
        "tools": rep["tools"],
        "input_tokens": round(mean_of("input_tokens")),
        "output_tokens": round(mean_of("output_tokens")),
        "total_tokens": round(mean_of("total_tokens")),
        "duration_s": round(mean_of("duration_s"), 1),
        "diagnoses": all_diags,
        "critique": rep.get("critique", ""),
        "outcome_rationale": rep.get("outcome_rationale", ""),
        "question": rep["question"],
        "answer": rep["answer"],
        "metric_specs": trial_rows[0]["metric_specs"],
    })
    return agg


async def evaluate_agent(
    agent: Any,
    cases: List[dict],
    metrics: Optional[Sequence[EvalMetric]] = None,
    judge_llm: Optional[Any] = None,
    concurrency: int = 4,
    trials: int = 1,
    verbose: bool = True,
    sandbox_root: Optional[str] = None,
) -> List[dict]:
    """골든 문항들을 병렬로 실행·채점합니다.

    - `metrics=None`이면 `PRESET_METRICS`(과정 3종 + 결과 3종)로 채점합니다.
    - `metrics=[...]`로 기본 메트릭과 커스텀 메트릭 리스트를 전달하면 해당 조합으로 채점합니다.
    - `trials > 1`이면 문항당 `trials`회 반복 실행하여 `pass@k`와 `pass^k`를 함께 집계합니다.
    """
    if metrics is not None and not isinstance(metrics, (list, tuple)):
        judge_llm, metrics = metrics, None

    active_metrics = list(metrics) if metrics is not None else list(PRESET_METRICS)
    if judge_llm is None:
        judge_llm = init_chat_model(model=JUDGE_MODEL, temperature=0.0)

    judge = HarnessJudge(judge_llm=judge_llm, strict=True)
    semaphore = asyncio.Semaphore(max(1, int(concurrency)))
    num_trials = max(1, int(trials))

    async def run_one_trial(case: dict) -> dict:
        async with semaphore:
            record = await run_case(agent, case, sandbox_root=sandbox_root)
            return await score_case_with_metrics(case, record, active_metrics, judge_llm, judge)

    async def run_case_trials(case: dict) -> dict:
        trial_rows = await asyncio.gather(*(run_one_trial(case) for _ in range(num_trials)))
        agg = _aggregate_trial_rows(case, list(trial_rows), active_metrics)
        if verbose:
            verdict = "통과" if agg["passed"] else "미달"
            trial_note = f" | pass@{num_trials}={agg['pass_at_k']:.0%}, pass^{num_trials}={agg['pass_pow_k']:.0%}" if num_trials > 1 else ""
            print(
                f"  ✔ {agg['id']:<8} 종합 {agg['composite']:.2f} ({verdict}) "
                f"| 도구 {agg['tool_calls']}회 | {agg['duration_s']}s{trial_note}"
            )
        return agg

    rows = await asyncio.gather(*(run_case_trials(c) for c in cases))
    return sorted(rows, key=lambda r: r["composite"])


def _resolve_metric_specs(
    rows: List[dict],
    metrics: Optional[Sequence[EvalMetric]] = None,
) -> Optional[List[Dict[str, Any]]]:
    if metrics is not None:
        return [m.to_spec() for m in metrics]
    if rows and "metric_specs" in rows[0]:
        return rows[0]["metric_specs"]
    return None


def summary_line(rows: List[dict]) -> str:
    """평가 전체를 한 줄로 요약합니다."""
    if not rows:
        return "평가 문항 없음"
    n = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    mean = lambda k: sum(float(r.get(k, 0.0)) for r in rows) / n
    base = (
        f"평균 종합 {mean('composite'):.3f} | 통과 {passed}/{n} (기준 {PASS_THRESHOLD}) | "
        f"평균 도구 {mean('tool_calls'):.1f}회 | 평균 토큰 {mean('total_tokens'):,.0f} | "
        f"평균 소요 {mean('duration_s'):.1f}s"
    )
    trials = rows[0].get("trials", 1)
    if trials > 1:
        base += f" | pass@{trials} {mean('pass_at_k'):.1%} | pass^{trials} {mean('pass_pow_k'):.1%}"
    return base


def results_table(rows: List[dict], metrics: Optional[Sequence[EvalMetric]] = None):
    """문항별 통합 점수 표(DataFrame). 점수가 낮은 문항부터 정렬합니다."""
    import pandas as pd

    df = pd.DataFrame(rows).sort_values("composite")
    df["verdict"] = df["passed"].map({True: "통과", False: "미달"})
    df["diagnosis"] = df["diagnoses"].map(lambda d: ", ".join(d) if d else "-")

    specs = _resolve_metric_specs(rows, metrics) or [m.to_spec() for m in PRESET_METRICS]
    columns = [
        ("id", "문항"),
        ("category", "유형"),
        ("composite", "종합"),
        *((s["name"], s["label"]) for s in specs if s["name"] in df.columns),
        ("tool_calls", "호출 수"),
    ]
    if "total_tokens" in df.columns:
        columns.append(("total_tokens", "토큰"))
    columns.extend([
        ("duration_s", "소요(s)"),
        ("verdict", "판정"),
        ("diagnosis", "진단 (기준 미달 지표)"),
    ])
    keys, _ = zip(*columns)
    return df[list(keys)].rename(columns=dict(columns)).reset_index(drop=True)


def diagnosis_table(rows: List[dict], metrics: Optional[Sequence[EvalMetric]] = None):
    """진단 항목별로 기준 미달 문항과 의심 하네스 계층을 집계합니다 (DataFrame)."""
    import pandas as pd

    specs = _resolve_metric_specs(rows, metrics) or [m.to_spec() for m in PRESET_METRICS]
    table = []
    for s in specs:
        if s.get("threshold") is None:
            continue
        diag_name = s["diagnosis"]
        hits = [r["id"] for r in sorted(rows, key=lambda x: x["id"]) if diag_name in (r.get("diagnoses") or [])]
        table.append({
            "진단": diag_name,
            "지표 (기준)": f"{s['name']} < {s['threshold']}",
            "해당 문항 수": len(hits),
            "해당 문항": ", ".join(hits) or "-",
            "의심할 계층": s.get("suspect_layer") or "-",
        })

    hits = [r["id"] for r in sorted(rows, key=lambda x: x["id"]) if "호출 한도 초과" in (r.get("diagnoses") or [])]
    table.append({
        "진단": "호출 한도 초과",
        "지표 (기준)": f"실행 단계 > {RECURSION_LIMIT}",
        "해당 문항 수": len(hits),
        "해당 문항": ", ".join(hits) or "-",
        "의심할 계층": "도구 인자(ACI), 탐색 중단 지침",
    })
    return pd.DataFrame(table)


def summarize(rows: List[dict]) -> str:
    """CLI 출력용 텍스트 요약."""
    return (
        summary_line(rows)
        + "\n\n"
        + results_table(rows).to_string(index=False)
        + "\n\n"
        + diagnosis_table(rows).to_string(index=False)
    )


def compare_table(before: List[dict], after: List[dict]):
    """두 실행의 문항별 종합 점수, 도구 호출 수, 소요 시간을 비교해 개선과 회귀를 판정합니다."""
    import pandas as pd

    prev = {r["id"]: r for r in before}
    table = []
    for r in sorted(after, key=lambda x: x["id"]):
        if r["id"] not in prev:
            continue
        p = prev[r["id"]]
        delta = round(r["composite"] - p["composite"], 2)
        call_diff = p["tool_calls"] - r["tool_calls"]
        if delta <= -NOISE_BAND:
            verdict = "회귀 ⚠️"
        elif delta >= NOISE_BAND:
            verdict = "개선"
        elif (delta >= -0.02 and call_diff >= 2) or (delta >= 0.03 and call_diff >= 1):
            verdict = "개선 (호출 절감)"
        else:
            verdict = "유지"
        table.append({
            "문항": r["id"],
            "종합 (전)": p["composite"],
            "종합 (후)": r["composite"],
            "변화": delta,
            "호출 수 (전)": p["tool_calls"],
            "호출 수 (후)": r["tool_calls"],
            "소요(s) (전)": p["duration_s"],
            "소요(s) (후)": r["duration_s"],
            "판정": verdict,
        })
    return pd.DataFrame(table)


def save_report(rows: List[dict], agent_name: str = "main_agent") -> str:
    """평가 결과 리포트를 `artifacts/eval_runs/` 아래 JSON 파일로 저장합니다."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"{agent_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"agent": agent_name, "created_at": datetime.now().isoformat(), "rows": rows},
            f,
            ensure_ascii=False,
            indent=2,
        )
    return path


def compare_reports(previous_path: str, rows: List[dict]) -> str:
    """저장된 이전 리포트와 현재 결과를 비교한 표 문자열을 반환합니다."""
    with open(previous_path, "r", encoding="utf-8") as f:
        before = json.load(f)["rows"]
    return compare_table(before, rows).to_string(index=False)


async def _main(args: argparse.Namespace) -> int:
    cases = load_golden(path=args.dataset, ids=args.ids)
    print(f"🧪 {args.agent} 오프라인 평가 시작: {len(cases)}문항 (trials={args.trials})")

    if args.use_app_factory:
        agent = await load_app_agent(args.agent)
    else:
        agent = build_main_agent_for_eval()

    try:
        rows = await evaluate_agent(
            agent,
            cases,
            concurrency=args.concurrency,
            trials=args.trials,
        )
    finally:
        cp = getattr(agent, "checkpointer", None)
        conn = getattr(cp, "conn", None) if cp is not None else None
        if conn is not None and getattr(conn, "_running", False):
            await conn.close()
        shutil.rmtree(os.path.join(PROJECT_ROOT, "artifacts", "eval_sandbox"), ignore_errors=True)
        shutil.rmtree(os.path.join(PROJECT_ROOT, "artifacts", "users", "eval_runner"), ignore_errors=True)

    print("\n" + summarize(rows))
    path = save_report(rows, args.agent)
    print(f"\n💾 리포트 저장: {os.path.relpath(path, PROJECT_ROOT)}")

    exit_code = 0
    if args.compare:
        with open(args.compare, "r", encoding="utf-8") as f:
            before_rows = json.load(f)["rows"]
        comp_df = compare_table(before_rows, rows)
        print("\n📊 이전 실행과 비교\n" + comp_df.to_string(index=False))
        regressions = int((comp_df["판정"] == "회귀 ⚠️").sum()) if not comp_df.empty else 0
        if args.fail_on_regression and regressions > 0:
            print(f"\n⛔ [CI Gate 실패] 회귀 문항 {regressions}건 감지!")
            exit_code = 1

    if args.min_pass_rate is not None and rows:
        pass_rate = sum(1 for r in rows if r["passed"]) / len(rows)
        if pass_rate < args.min_pass_rate:
            print(f"\n⛔ [CI Gate 실패] 통과율 {pass_rate:.1%} < 기준 {args.min_pass_rate:.1%}")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harness Agent offline evaluation runner")
    parser.add_argument("--agent", default="main_agent", help="대상 에이전트 이름 (기본: main_agent)")
    parser.add_argument("--dataset", default=GOLDEN_PATH, help="평가 데이터셋 JSON 경로")
    parser.add_argument("--use-app-factory", action="store_true", help="app/agents/<agent> 전체 팩토리 사용")
    parser.add_argument("--ids", nargs="*", default=None, help="평가할 문항 id (생략 시 전체)")
    parser.add_argument("--concurrency", type=int, default=4, help="동시 실행 문항 수")
    parser.add_argument("--trials", type=int, default=1, help="문항당 반복 실행 횟수 (pass@k / pass^k)")
    parser.add_argument("--compare", default=None, help="비교할 이전 리포트 JSON 경로")
    parser.add_argument("--fail-on-regression", action="store_true", help="회귀 문항 발생 시 exit code 1 반환")
    parser.add_argument("--min-pass-rate", type=float, default=None, help="최소 통과율 기준 (예: 0.8)")
    raise SystemExit(asyncio.run(_main(parser.parse_args())))
