"""
tests/test_evaluation_harness.py
================================
평가 하네스(app/evaluate/*, app/middleware/evaluator/*, message_markers, golden dataset)
단위 및 통합 검증 스위트 (외부 네트워크/API 호출 없이 결정론적 실행).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.evaluate import (
    EvalMetric,
    EvalSample,
    HarnessJudge,
    OutcomeEvaluation,
    PRESET_METRICS,
    TrajectoryEvaluation,
    build_main_agent_for_eval,
    compare_table,
    evaluate_system_prompt,
    hill_climbing_optimize,
    load_golden,
    metrics_table,
    mine_cases_from_audit_logs,
)
from app.middleware.evaluator import (
    EvaluatorHarness,
    JudgeVerdict,
    extract_current_turn_messages,
    extract_last_ai_answer,
    extract_tool_contexts,
    extract_user_query,
    format_turn_trajectory,
)
from app.middleware.memory.episodic_store import _records_from_messages
from app.middleware.memory.transcript_store import classify_message
from app.utils.message_markers import (
    EVALUATOR_FEEDBACK_TAG,
    ORIGIN_EVALUATOR_FEEDBACK,
    is_evaluator_feedback,
    is_user_turn_start,
    origin_kwargs,
)


class _StubStructuredJudge:
    """with_structured_output() 호출마다 시퀀스 순서대로 응답을 반환하는 결정론적 테스트용 판사."""

    def __init__(self, responses: List[Any]):
        self._responses = list(responses)
        self.calls: List[Any] = []

    def with_structured_output(self, schema: Any):
        parent = self

        def _invoke(inp: Any, config: Any = None):
            parent.calls.append((schema, inp))
            if not parent._responses:
                raise RuntimeError("No stubbed judge responses left")
            resp = parent._responses.pop(0)
            return resp(inp) if callable(resp) else resp

        async def _ainvoke(inp: Any, config: Any = None):
            return _invoke(inp, config)

        stub = MagicMock()
        stub.invoke = _invoke
        stub.ainvoke = _ainvoke
        return stub


def test_message_markers_and_transcript_isolation():
    """EvaluatorHarness 피드백은 사용자 턴 경계에서 제외되고 transcript kind='internal'로 분류된다."""
    u1 = HumanMessage(content="첫 질문")
    a1 = AIMessage(content="부족한 초안")
    fb = HumanMessage(
        content=f"⚠️ {EVALUATOR_FEEDBACK_TAG} Rework Required",
        additional_kwargs=origin_kwargs(ORIGIN_EVALUATOR_FEEDBACK),
    )
    a2 = AIMessage(content="보완된 최종 답변")

    assert is_user_turn_start(u1) is True
    assert is_user_turn_start(fb) is False
    assert is_evaluator_feedback(fb) is True

    # 태그만으로 판별하는 하위 호환 경로도 동작해야 함
    fb_by_tag = HumanMessage(content=f"⚠️ {EVALUATOR_FEEDBACK_TAG} tag-only fallback")
    assert is_evaluator_feedback(fb_by_tag) is True
    assert is_user_turn_start(fb_by_tag) is False

    assert classify_message(u1) == "user"
    assert classify_message(fb) == "internal"

    records = _records_from_messages([u1, a1, fb, a2])
    kinds = [r["kind"] for r in records]
    assert kinds == ["user", "assistant", "internal", "assistant"]


def test_turn_slicing_and_trajectory_formatting():
    """멀티턴 대화에서 현재 턴만 추출하고 tool_calls를 누락 없이 포맷한다."""
    msgs = [
        HumanMessage(content="이전 턴 질문"),
        AIMessage(content="이전 턴 답변"),
        HumanMessage(content="현재 턴 질문"),
        AIMessage(content="", tool_calls=[{"name": "file_read", "args": {"file_path": "a.json"}, "id": "tc1"}]),
        ToolMessage(content='{"ok": true}', tool_call_id="tc1", name="file_read"),
        HumanMessage(
            content=f"⚠️ {EVALUATOR_FEEDBACK_TAG} 피드백",
            additional_kwargs=origin_kwargs(ORIGIN_EVALUATOR_FEEDBACK),
        ),
        AIMessage(content="현재 턴 최종 답변"),
    ]
    turn = extract_current_turn_messages(msgs)
    assert len(turn) == 5
    assert extract_user_query(msgs) == "현재 턴 질문"
    assert extract_last_ai_answer(msgs) == "현재 턴 최종 답변"
    assert extract_tool_contexts(msgs) == ['{"ok": true}']

    traj_txt = format_turn_trajectory(turn[:-1])
    assert "이전 턴 질문" not in traj_txt
    assert "file_read" in traj_txt
    assert '"file_path": "a.json"' in traj_txt


def test_eval_metric_caching_and_tables():
    """EvalMetric 자동 인자 주입, 문항당 Judge 1회 캐싱, metrics_table/compare_table 검증."""
    stub_judge_llm = _StubStructuredJudge([
        OutcomeEvaluation(
            rationale="정답 및 근거 일치",
            task_completion=0.9,
            factual_grounding=0.85,
            answer_relevance=1.0,
        ),
        TrajectoryEvaluation(
            critique="적합한 도구 최소 호출",
            tool_selection_accuracy=1.0,
            argument_quality_score=1.0,
            step_economy_score=1.0,
            error_recovery_score=1.0,
        ),
    ])
    judge = HarnessJudge(judge_llm=stub_judge_llm, strict=True)
    sample = EvalSample(
        id="t-01",
        category="테스트",
        question="질문",
        ground_truth="정답",
        target_tools=["file_read"],
        answer="답변",
        contexts=["컨텍스트"],
        trajectory=[{"tool_name": "file_read", "arguments": {}, "status": "ok", "response_snippet": "ok"}],
    )

    def sync_code_metric(answer: str, tool_calls: int) -> float:
        return 1.0 if answer and tool_calls == 1 else 0.0

    async def async_custom_metric(question: str, answer: str) -> dict:
        return {"score": 0.75, "note": f"{question}->{answer}"}

    custom_code = EvalMetric(name="code_chk", label="코드검사", fn=sync_code_metric, weight=0.1, threshold=0.5)
    custom_async = EvalMetric(name="async_chk", label="비동기검사", fn=async_custom_metric, weight=0.1, threshold=0.5)

    async def _run():
        metrics = PRESET_METRICS + [custom_code, custom_async]
        scores = await asyncio.gather(*(m.aevaluate(sample, judge=judge) for m in metrics))
        return metrics, scores

    metrics, scores = asyncio.run(_run())
    # PRESET_METRICS 6개가 outcome 1회 + trajectory 1회만 호출해야 함
    assert len(stub_judge_llm.calls) == 2
    assert scores[-2][0] == 1.0
    assert scores[-1][0] == 0.75

    df_m = metrics_table(metrics)
    assert len(df_m) == len(metrics)

    before = [
        {"id": "c1", "composite": 0.90, "tool_calls": 2, "duration_s": 2.0},
        {"id": "c2", "composite": 0.85, "tool_calls": 6, "duration_s": 10.0},
        {"id": "c3", "composite": 0.90, "tool_calls": 3, "duration_s": 3.0},
        {"id": "c4", "composite": 0.70, "tool_calls": 3, "duration_s": 4.0},
    ]
    after = [
        {"id": "c1", "composite": 0.75, "tool_calls": 2, "duration_s": 2.0},  # -0.15 -> 회귀
        {"id": "c2", "composite": 0.86, "tool_calls": 2, "duration_s": 4.0},  # call_diff=4 -> 개선 (호출 절감)
        {"id": "c3", "composite": 0.92, "tool_calls": 3, "duration_s": 3.0},  # 유지
        {"id": "c4", "composite": 0.85, "tool_calls": 2, "duration_s": 3.0},  # +0.15 -> 개선
    ]
    comp = compare_table(before, after).set_index("문항")
    assert comp.loc["c1", "판정"] == "회귀 ⚠️"
    assert comp.loc["c2", "판정"] == "개선 (호출 절감)"
    assert comp.loc["c3", "판정"] == "유지"
    assert comp.loc["c4", "판정"] == "개선"


def test_evaluator_harness_rework_loop_and_circuit_breaker():
    """EvaluatorHarness(mode='rework')의 반려 → jump_to='model' 재작업 → 승인 및 max_reworks 한도 검증."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1) 반려 후 2번째 응답에서 승인되는 경우
        judge_llm = _StubStructuredJudge([
            JudgeVerdict(
                evidence="계산 근거 누락",
                reason="공식과 점수가 빠짐",
                is_approved=False,
                score=40,
                feedback="Value_Score 공식과 계산 점수를 포함하세요.",
            ),
            JudgeVerdict(
                evidence="공식과 50.95점 모두 포함됨",
                reason="요구사항 충족",
                is_approved=True,
                score=96,
                feedback="",
            ),
        ])
        ev = EvaluatorHarness(mode="rework", max_reworks=2, judge_llm=judge_llm, log_dir=tmpdir, verbose=False)
        fake_agent_llm = GenericFakeChatModel(messages=iter([
            AIMessage(content="LP-001이 1등입니다."),
            AIMessage(content="공식에 따른 LP-001 점수는 50.95점입니다."),
        ]))
        agent = create_agent(model=fake_agent_llm, tools=[], middleware=[ev])

        res = asyncio.run(agent.ainvoke(
            {"messages": [HumanMessage(content="LP-001 점수 보고")]},
            config={"configurable": {"thread_id": "test-rework-ok"}},
        ))
        assert "50.95점" in res["messages"][-1].content
        assert len(ev.verdict_history) == 2
        assert ev.verdict_history[0]["is_approved"] is False
        assert ev.verdict_history[1]["is_approved"] is True
        assert sum(1 for m in res["messages"] if is_user_turn_start(m)) == 1
        assert sum(1 for m in res["messages"] if is_evaluator_feedback(m)) == 1

        # 2) 계속 반려되어도 max_reworks=1 서킷 브레이커에서 안전 종료되는지 검증
        judge_always_reject = _StubStructuredJudge([
            JudgeVerdict(evidence="부족", reason="반려1", is_approved=False, score=30, feedback="고쳐주세요"),
            JudgeVerdict(evidence="여전히 부족", reason="반려2", is_approved=False, score=35, feedback="한도 초과"),
        ])
        ev_cap = EvaluatorHarness(mode="rework", max_reworks=1, judge_llm=judge_always_reject, log_dir=tmpdir, verbose=False)
        fake_agent_llm_2 = GenericFakeChatModel(messages=iter([
            AIMessage(content="초안 1"),
            AIMessage(content="재작성 2"),
        ]))
        agent_cap = create_agent(model=fake_agent_llm_2, tools=[], middleware=[ev_cap])
        res_cap = asyncio.run(agent_cap.ainvoke(
            {"messages": [HumanMessage(content="테스트")]},
            config={"configurable": {"thread_id": "test-rework-cap"}},
        ))
        assert res_cap["messages"][-1].content == "재작성 2"
        assert len(ev_cap.verdict_history) == 2


def test_evaluator_harness_shadow_mode_and_log_mining():
    """EvaluatorHarness(mode='shadow') 비동기 JSONL 적재 및 mine_cases_from_audit_logs 추출 검증."""
    with tempfile.TemporaryDirectory() as tmpdir:
        judge_llm = _StubStructuredJudge([
            JudgeVerdict(
                evidence="답변 근거 미흡",
                reason="파일명 미인용 및 계산 누락",
                is_approved=False,
                score=55,
                feedback="근거 파일명을 명시하세요.",
            )
        ])
        shadow_ev = EvaluatorHarness(
            mode="shadow",
            sample_rate=1.0,
            judge_llm=judge_llm,
            log_dir=tmpdir,
            verbose=False,
        )
        fake_llm = GenericFakeChatModel(messages=iter([AIMessage(content="대략 100원입니다.")]))
        agent = create_agent(model=fake_llm, tools=[], middleware=[shadow_ev])

        async def _run():
            await agent.ainvoke(
                {"messages": [HumanMessage(content="laptops_market_data.json 요약해줘")]},
                config={"configurable": {"thread_id": "shadow-t1"}},
            )
            await shadow_ev.await_pending(timeout=5.0)

        asyncio.run(_run())

        stream_file = Path(tmpdir) / "eval_audit_stream.jsonl"
        assert stream_file.exists()
        lines = [json.loads(ln) for ln in stream_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1
        assert lines[0]["mode"] == "shadow"
        assert lines[0]["score"] == 55

        # AgentLogTracer turn_summary 샘플 파일도 함께 생성하여 join + mining 검증
        audit_file = Path(tmpdir) / "audit.jsonl"
        audit_file.write_text(
            json.dumps({
                "event": "turn_summary",
                "session_id": "shadow-t1",
                "status": "SUCCESS",
                "user_query": "laptops_market_data.json 요약해줘",
                "final_response": "대략 100원입니다.",
                "total_tool_calls": 6,
                "steps": [{"type": "tool_call", "tool_name": "file_read"}],
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        mined = mine_cases_from_audit_logs(tmpdir, min_tool_calls=5, max_score=75)
        assert len(mined) == 1
        assert mined[0]["question"] == "laptops_market_data.json 요약해줘"
        assert mined[0]["source_telemetry"]["judge_score"] == 55
        assert mined[0]["source_telemetry"]["tool_calls"] == 6


def test_optimizer_train_val_split_and_length_penalty():
    """optimizer.py가 Train/Val 분리 및 길이 페널티 목적함수로 프롬프트를 평가/선택하는지 검증."""
    dummy_model = RunnableLambda(lambda x: AIMessage(content="응답"))
    dummy_proposer = RunnableLambda(lambda x: AIMessage(content="구체적 지침을 포함한 개선 프롬프트"))
    judge_llm = _StubStructuredJudge([
        # Iteration 0: train (1), val (1)
        JudgeVerdict(evidence="부족", reason="누락", is_approved=False, score=50, feedback="수치 인용"),
        JudgeVerdict(evidence="부족", reason="누락", is_approved=False, score=50, feedback="수치 인용"),
        # Iteration 1: train (1), val (1)
        JudgeVerdict(evidence="충분", reason="통과", is_approved=True, score=90, feedback=""),
        JudgeVerdict(evidence="충분", reason="통과", is_approved=True, score=90, feedback=""),
    ])

    train = [{"id": "tr1", "query": "Q1", "tool_context": "C1", "requirements": "R1"}]
    val = [{"id": "v1", "query": "Q2", "tool_context": "C2", "requirements": "R2"}]

    best, hist = hill_climbing_optimize(
        baseline="기본 프롬프트",
        dataset=train,
        val_dataset=val,
        model=dummy_model,
        proposer_llm=dummy_proposer,
        judge_llm=judge_llm,
        length_penalty_alpha=0.1,
        max_iterations=1,
        target_score=95.0,
        verbose=False,
    )
    assert len(hist) == 2
    assert hist[1]["accepted"] is True
    assert best == "구체적 지침을 포함한 개선 프롬프트"
    assert hist[1]["objective_score"] == pytest.approx(90.0 - 0.1 * len(best), abs=1e-3)


def test_golden_dataset_integrity_and_eval_agent_builder():
    """골든 데이터셋 10문항 규격, 참조 파일 존재 여부, main_agent 평가 빌더 무결성 검증."""
    cases = load_golden()
    assert len(cases) == 10
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == 10
    assert {"data-01", "calc-01", "cafe-01", "code-01", "cfg-01", "err-01", "art-01", "plan-01", "skill-01", "neg-01"} == set(ids)

    expected_existing = [
        "artifacts/notebooks/data/laptops_market_data.json",
        "artifacts/notebooks/data/specs_criteria.json",
        "artifacts/notebooks/data/backup_laptops_catalog.json",
        "artifacts/notebooks/data/corrupted_catalog.bin",
        "artifacts/notebooks/cafe_data/districts.json",
        "artifacts/notebooks/cafe_data/backup_survey.json",
        "artifacts/notebooks/cafe_data/scoring_weights.json",
        "app/utils/message_markers.py",
        "app/agents/main_agent/skills/pdf_processing/SKILL.md",
        "configs/model.config",
    ]
    for rel in expected_existing:
        assert os.path.exists(os.path.join(project_root, rel)), f"Missing fixture: {rel}"

    fake_llm = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    agent = build_main_agent_for_eval(model=fake_llm)
    assert agent is not None
    assert "tools" in agent.nodes

    # Gemini API 함수 스키마 변환 호환성 검증 (예: integer Literal enum 충돌 재발 방지)
    from langchain_google_genai._function_utils import convert_to_genai_function_declarations
    from tests.agent_inspector import extract_agent_tools

    bound_tools = extract_agent_tools(agent)
    bound_names = {getattr(t, "name", "") for t in bound_tools}
    expected_core = {
        "enter_plan",
        "exit_plan",
        "task_create",
        "task_list",
        "task_update",
        "file_read",
        "file_writer",
        "file_edit",
        "grep_search",
        "glob_search",
        "bash_command",
    }
    assert expected_core <= bound_names
    assert "roll_dice" not in bound_names
    genai_tools = convert_to_genai_function_declarations(bound_tools)
    fn_decls = [fd for gt in genai_tools for fd in (gt.function_declarations or [])]
    assert len(fn_decls) == len(bound_tools)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
