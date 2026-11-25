"""
app/evaluate/dataset_builder.py
===============================
1) 시드(EvalSeed) 기반 평가 데이터셋 생성 및 타 계열 판사 모델 검수
2) 운영 로그(AgentLogTracer audit.jsonl / EvaluatorHarness eval_audit_stream.jsonl)에서
   실패·비효율 턴을 추출해 골든 회귀 데이터셋 후보를 생성하는 피드백 루프(Failure Mining)
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.middleware.evaluator.evaluator import DEFAULT_JUDGE_MODEL
from app.utils import init_chat_model

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


@dataclass
class EvalSeed:
    """평가 문항 1건을 생성하기 위한 시드(Seed) 명세."""

    id: str
    category: str
    topic: str
    scenario: str
    source_files: List[str]
    target_tools: List[str] = field(default_factory=list)
    section_keyword: Optional[str] = None
    max_chars_per_file: int = 3500


class GeneratedCaseSchema(BaseModel):
    """시드로부터 생성된 평가 문항 초안 스키마."""

    question: str = Field(
        description="실제 사용자가 요청하는 것처럼 완결된 질문 ('위 표에서', '첨부 파일처럼' 같은 암묵적 지시어 대신 정확한 대상 경로/조건 명시)"
    )
    ground_truth: str = Field(
        description="채점 기준이 되는 정답 (정확한 수치, 계산 과정, 대상 파일명/심볼명, 미존재 유형의 경우 확인되지 않음 안내 포함)"
    )
    evidence_quote: str = Field(
        description="정답의 근거가 되는 원천 파일 핵심 발췌 또는 확인한 파일 범위"
    )


class CaseQualityVerdict(BaseModel):
    """생성된 평가 문항에 대한 CoT-First 판사 모델 검수 결과."""

    reason: str = Field(
        description="원천 파일과 초안 대조 후 판단한 검수 사유 및 담당자 확인 포인트 (1~2문장)"
    )
    is_grounded: bool = Field(
        description="정답(ground_truth)의 수치·조건·결론이 원천 파일과 정확히 일치하며 임의 추측이 없는가"
    )
    is_standalone: bool = Field(
        description="원천 파일을 미리 보지 않고 질문(question)만 읽어도 대상 파일과 요구 조건이 명확한가"
    )
    is_clear_rubric: bool = Field(
        description="채점자가 일관되게 정오를 판정할 수 있도록 정답 기준이 모호하지 않은가"
    )


_CASE_GEN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 AI 에이전트 평가 데이터셋을 작성하는 하네스 엔지니어입니다.\n"
        "제공된 [시드 명세]와 [원천 파일 발췌]만을 근거로 평가 문항 1건을 작성하세요.\n\n"
        "작성 원칙:\n"
        "1. 질문 독립성: 질문만 읽어도 에이전트가 어떤 파일이나 디렉토리를 확인해야 하는지 명확해야 합니다. 원천 파일 경로를 질문에 자연스럽게 포함하세요.\n"
        "2. 원문 근거 엄수: 원천 파일에 적힌 수치·필드명·심볼명·설정값만 사용하세요. 없는 값을 추측해 넣지 마세요.\n"
        "3. 유형별 주의사항:\n"
        "   - '존재하지 않는 데이터/정보' 유형은 원천 폴더/파일에 실제로 없는 항목을 묻고, 정답에는 확인되지 않으며 없는 수치를 지어내지 않아야 함을 명시하세요.\n"
        "   - '계산/집계' 유형은 중간 계산 과정과 최종 수치를 정답에 함께 적으세요.",
    ),
    (
        "human",
        "[시드 명세]\n"
        "- 문항 ID: {seed_id}\n"
        "- 평가 유형: {category}\n"
        "- 주제(Topic): {topic}\n"
        "- 시나리오 지침: {scenario}\n"
        "- 기대 호출 도구: {target_tools}\n\n"
        "[원천 파일 발췌]\n{source_context}",
    ),
])

_CASE_VERIFY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 평가 데이터셋 품질 검수자입니다. 먼저 [시드 명세] 및 [원천 파일 발췌]와 [평가 문항 초안]을 대조하여 `reason`에 검수 근거를 적고,\n"
        "이어서 `is_grounded`, `is_standalone`, `is_clear_rubric`을 판정하세요.\n"
        "- '존재하지 않는 정보' 유형은 원천 파일에 해당 항목이 실제로 없고 정답이 미존재 안내를 요구한다면 is_grounded=True입니다.",
    ),
    (
        "human",
        "[시드 명세]\n"
        "- 평가 유형: {category}\n"
        "- 주제: {topic}\n"
        "- 시나리오 지침: {scenario}\n\n"
        "[원천 파일 발췌]\n{source_context}\n\n"
        "[평가 문항 초안]\n{candidate_json}",
    ),
])


def load_seed_context(seed: EvalSeed, project_root: str = PROJECT_ROOT) -> str:
    """시드에 지정된 원천 파일들에서 관련 구간을 읽어 하나의 참조 문자열로 묶습니다."""
    excerpts = []
    for rel_path in seed.source_files:
        abs_path = rel_path if os.path.isabs(rel_path) else os.path.join(project_root, rel_path)
        with open(abs_path, "r", encoding="utf-8") as f:
            raw = f.read()

        if seed.section_keyword and seed.section_keyword in raw:
            pos = max(0, raw.find(seed.section_keyword) - 150)
            snippet = raw[pos : pos + seed.max_chars_per_file]
        else:
            snippet = raw[: seed.max_chars_per_file]

        excerpts.append(f"[{rel_path} 발췌]\n{snippet.strip()}")
    return "\n\n".join(excerpts)


async def generate_from_seeds(
    seeds: Sequence[EvalSeed],
    llm: Optional[Any] = None,
    concurrency: int = 4,
    project_root: str = PROJECT_ROOT,
) -> List[dict]:
    """시드 목록으로부터 평가 문항 초안을 병렬 생성합니다."""
    if llm is None:
        llm = init_chat_model(model="gemini-3.8-flash", temperature=0.0)

    chain = _CASE_GEN_PROMPT | llm.with_structured_output(GeneratedCaseSchema)
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(seed: EvalSeed) -> dict:
        async with semaphore:
            source_context = load_seed_context(seed, project_root=project_root)
            raw = await chain.ainvoke({
                "seed_id": seed.id,
                "category": seed.category,
                "topic": seed.topic,
                "scenario": seed.scenario,
                "target_tools": ", ".join(seed.target_tools),
                "source_context": source_context,
            })
            generated = GeneratedCaseSchema(**raw) if isinstance(raw, dict) else raw
            return {
                "id": seed.id,
                "category": seed.category,
                "topic": seed.topic,
                "question": generated.question,
                "ground_truth": generated.ground_truth,
                "evidence_quote": generated.evidence_quote,
                "target_tools": list(seed.target_tools),
            }

    return list(await asyncio.gather(*(_one(s) for s in seeds)))


async def verify_generated_cases(
    cases: Sequence[dict],
    seeds: Sequence[EvalSeed],
    judge_llm: Optional[Any] = None,
    concurrency: int = 4,
    project_root: str = PROJECT_ROOT,
) -> Tuple[pd.DataFrame, List[dict]]:
    """생성된 문항 초안을 타 계열 판사 모델로 검수하고 (검수 요약 표, 통과 문항 리스트)를 반환합니다."""
    if judge_llm is None:
        judge_llm = init_chat_model(model=DEFAULT_JUDGE_MODEL, temperature=0.0)

    seed_map = {s.id: s for s in seeds}
    chain = _CASE_VERIFY_PROMPT | judge_llm.with_structured_output(CaseQualityVerdict)
    semaphore = asyncio.Semaphore(concurrency)

    async def _check(case: dict) -> Tuple[dict, Optional[dict]]:
        async with semaphore:
            seed = seed_map[case["id"]]
            source_context = load_seed_context(seed, project_root=project_root)
            raw = await chain.ainvoke({
                "category": seed.category,
                "topic": seed.topic,
                "scenario": seed.scenario,
                "source_context": source_context,
                "candidate_json": json.dumps(
                    {
                        "question": case["question"],
                        "ground_truth": case["ground_truth"],
                        "evidence_quote": case.get("evidence_quote", ""),
                        "target_tools": case["target_tools"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            })
            verdict = CaseQualityVerdict(**raw) if isinstance(raw, dict) else raw
            passed = bool(verdict.is_grounded and verdict.is_standalone and verdict.is_clear_rubric)
            row = {
                "문항 ID": case["id"],
                "유형": case["category"],
                "시드 주제": case.get("topic", seed.topic),
                "생성된 질문": case["question"],
                "기대 도구": case["target_tools"],
                "검수 판정": "통과" if passed else "보완 필요",
                "검수 의견": verdict.reason,
            }
            accepted = (
                {
                    "id": case["id"],
                    "category": case["category"],
                    "question": case["question"],
                    "ground_truth": case["ground_truth"],
                    "target_tools": case["target_tools"],
                }
                if passed
                else None
            )
            return row, accepted

    checked = await asyncio.gather(*(_check(c) for c in cases))
    summary_rows = [r for r, _ in checked]
    accepted_cases = [a for _, a in checked if a is not None]
    return pd.DataFrame(summary_rows), accepted_cases


# =============================================================================
# Observability → Evaluation Flywheel (Audit & Shadow Log Mining)
# =============================================================================

def _collect_jsonl_files(paths: Sequence[str]) -> List[str]:
    found: List[str] = []
    for p in paths:
        if not p:
            continue
        if os.path.isfile(p):
            found.append(p)
        elif os.path.isdir(p):
            found.extend(glob.glob(os.path.join(p, "*.jsonl")))
            found.extend(glob.glob(os.path.join(p, "**", "*.jsonl"), recursive=True))
    return sorted(dict.fromkeys(found))


def mine_cases_from_audit_logs(
    log_paths: Sequence[str] | str,
    min_tool_calls: int = 5,
    max_score: int = 75,
    max_cases: int = 10,
) -> List[dict]:
    """AgentLogTracer(`audit.jsonl`)와 EvaluatorHarness(`eval_audit_stream.jsonl`)에서
    실패·반려·과다 호출 턴을 추출해 골든 회귀 데이터셋 후보 리스트로 반환합니다.
    """
    paths = [log_paths] if isinstance(log_paths, str) else list(log_paths)
    files = _collect_jsonl_files(paths)

    turn_records: List[Dict[str, Any]] = []
    verdict_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    verdict_by_query: Dict[str, Dict[str, Any]] = {}

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    event = rec.get("event") or rec.get("type") or ""
                    if event == "turn_summary":
                        turn_records.append(rec)
                    elif event == "evaluator_verdict":
                        uq = str(rec.get("user_query") or "").strip()
                        key = (str(rec.get("session_id") or ""), uq)
                        verdict_by_key[key] = rec
                        if uq:
                            verdict_by_query[uq] = rec
        except OSError:
            continue

    candidates: List[Tuple[int, Dict[str, Any]]] = []
    seen_queries: set[str] = set()

    # 1. turn_summary 기준 스캔 (+ 매칭되는 evaluator_verdict 결합)
    for rec in turn_records:
        query = str(rec.get("user_query") or "").strip()
        if not query or query == "unknown" or query in seen_queries:
            continue

        sid = str(rec.get("session_id") or "")
        verdict = verdict_by_key.get((sid, query)) or verdict_by_query.get(query)
        status = str(rec.get("status") or "SUCCESS")
        last_error = rec.get("last_error")
        tool_calls = int(rec.get("total_tool_calls") or 0)
        score = verdict.get("score") if verdict else None
        is_approved = verdict.get("is_approved") if verdict else True

        reasons: List[str] = []
        priority = 0
        if status != "SUCCESS":
            reasons.append(f"status={status}")
            priority += 100
        if last_error:
            reasons.append(f"error={str(last_error)[:80]}")
            priority += 50
        if verdict and (not is_approved or (score is not None and score < max_score)):
            reasons.append(f"judge_score={score}")
            priority += 80
        if tool_calls >= min_tool_calls:
            reasons.append(f"high_tool_calls={tool_calls}")
            priority += 30 + tool_calls

        if not reasons:
            continue

        seen_queries.add(query)
        used_tools = list(
            dict.fromkeys(
                s.get("tool_name")
                for s in (rec.get("steps") or [])
                if isinstance(s, dict) and s.get("type") == "tool_call" and s.get("tool_name")
            )
        )
        gt_note = verdict.get("feedback") or verdict.get("reason") if verdict else ""
        candidates.append((
            priority,
            {
                "id": f"mined-{len(candidates) + 1:02d}",
                "category": "운영 로그 추출 (검수 필요)",
                "question": query,
                "ground_truth": (
                    f"[담당자 정답 확정 필요] 기존 응답 요약: {str(rec.get('final_response') or '')[:160]}"
                    + (f" | Judge 지적: {gt_note}" if gt_note else "")
                ),
                "target_tools": used_tools or ["file_read"],
                "source_telemetry": {
                    "session_id": sid,
                    "status": status,
                    "tool_calls": tool_calls,
                    "judge_score": score,
                    "reasons": reasons,
                },
            },
        ))

    # 2. turn_summary 없이 standalone evaluator_verdict만 있는 경우 보충
    for (sid, query), verdict in verdict_by_key.items():
        if not query or query in seen_queries:
            continue
        score = verdict.get("score")
        is_approved = bool(verdict.get("is_approved", True))
        if is_approved and (score is None or score >= max_score):
            continue
        seen_queries.add(query)
        candidates.append((
            80,
            {
                "id": f"mined-{len(candidates) + 1:02d}",
                "category": "런타임 자가 교정 반려/저점수 (검수 필요)",
                "question": query,
                "ground_truth": (
                    f"[담당자 정답 확정 필요] Judge 사유: {verdict.get('reason', '')} "
                    f"| 보완 지침: {verdict.get('feedback', '')}"
                ),
                "target_tools": [],
                "source_telemetry": {
                    "session_id": sid,
                    "status": "FLAGGED",
                    "tool_calls": None,
                    "judge_score": score,
                    "reasons": [f"judge_score={score}"],
                },
            },
        ))

    candidates.sort(key=lambda item: item[0], reverse=True)
    result = [case for _, case in candidates[:max_cases]]
    for idx, case in enumerate(result, 1):
        case["id"] = f"mined-{idx:02d}"
    return result
