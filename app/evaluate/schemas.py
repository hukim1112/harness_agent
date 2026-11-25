"""
app/evaluate/schemas.py
=======================
CoT-First 2계층(Trajectory + Outcome) 평가 스키마 및 범용 HarnessJudge.

- TrajectoryEvaluation: 도구 선택, 인자 품질, 호출 효율, 장애 복구 (LLM 채점, critique 선행)
- OutcomeEvaluation   : 과업 완결성, 근거 충실도, 질문 관련성 (LLM 채점, rationale 선행)
- 종합 점수(trajectory_score / outcome_score)는 코드 가중합(@computed_field)으로 결정론적 계산
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, computed_field

from app.middleware.evaluator.evaluator import DEFAULT_JUDGE_MODEL
from app.utils import init_chat_model

TRAJECTORY_WEIGHTS: Dict[str, float] = {
    "tool_selection_accuracy": 0.30,
    "argument_quality_score": 0.25,
    "step_economy_score": 0.25,
    "error_recovery_score": 0.20,
}

OUTCOME_WEIGHTS: Dict[str, float] = {
    "task_completion": 0.45,
    "factual_grounding": 0.35,
    "answer_relevance": 0.20,
}


def _weighted(model: BaseModel, weights: Dict[str, float]) -> float:
    return round(sum(float(getattr(model, k)) * w for k, w in weights.items()), 3)


class TrajectoryEvaluation(BaseModel):
    """과정(Tool Trajectory) CoT-First 채점 스키마. trajectory_score는 코드에서 계산합니다."""

    critique: str = Field(
        description="점수를 매기기 전에 쓰는 과정 감사 의견 (2~3문장). 호출마다 어떤 정보를 얻으려 했고 중복·과잉 탐색·장애 복구가 있었는지 먼저 적습니다."
    )
    tool_selection_accuracy: float = Field(
        ge=0.0,
        le=1.0,
        description="질문/과업에 적합한 도구를 선택했는가? (0.0 ~ 1.0)",
    )
    argument_quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="도구 인자(파일 경로, 검색 패턴, 명령어, 계획 단계)가 정확하고 명확했는가? (0.0 ~ 1.0)",
    )
    step_economy_score: float = Field(
        ge=0.0,
        le=1.0,
        description="불필요한 반복 호출이나 과잉 탐색 없이 적정 스텝으로 해결했는가? (0.0 ~ 1.0)",
    )
    error_recovery_score: float = Field(
        ge=0.0,
        le=1.0,
        description="도구 오류 발생 시 원인을 파악해 대안을 찾아 복구했는가? (오류 없이 정상 완료된 경우도 1.0) (0.0 ~ 1.0)",
    )

    @computed_field
    @property
    def trajectory_score(self) -> float:
        return _weighted(self, TRAJECTORY_WEIGHTS)


class OutcomeEvaluation(BaseModel):
    """결과(Outcome) CoT-First 채점 스키마. outcome_score는 코드에서 계산합니다."""

    rationale: str = Field(
        description="점수를 매기기 전에 쓰는 대조 메모 (3~5문장). Ground Truth의 핵심 사실을 하나씩 답변과 대조하고, 답변의 주장이 도구 관측 결과(Contexts)에 근거하는지 적습니다."
    )
    task_completion: float = Field(
        ge=0.0,
        le=1.0,
        description="과업 완결성: 답변의 핵심 사실(수치, 계산 결과, 파일·심볼명, 산출물 요약, 미존재 결론)이 Ground Truth와 일치하는가? (0.0 ~ 1.0)",
    )
    factual_grounding: float = Field(
        ge=0.0,
        le=1.0,
        description="근거 충실도: 답변의 모든 주장과 수치가 실행 중 관측된 도구 결과에 근거하는가? (환각 0% 및 정당한 미존재 안내 = 1.0) (0.0 ~ 1.0)",
    )
    answer_relevance: float = Field(
        ge=0.0,
        le=1.0,
        description="답변 관련성: 답변이 사용자 질문과 요구 형식에 직접 답하는가? (0.0 ~ 1.0)",
    )

    @computed_field
    @property
    def outcome_score(self) -> float:
        return _weighted(self, OUTCOME_WEIGHTS)


def _coerce_model(raw: Any, schema: type[BaseModel]) -> Any:
    if isinstance(raw, schema):
        return raw
    if isinstance(raw, dict):
        return schema(**raw)
    if hasattr(raw, "model_dump"):
        return schema(**raw.model_dump())
    raise TypeError(f"Unsupported structured judge output: {type(raw)}")


class HarnessJudge:
    """오프라인 벤치마크용 2계층(Trajectory + Outcome) 통합 판사 엔진."""

    def __init__(
        self,
        judge_llm: Optional[Any] = None,
        judge_model_name: str = DEFAULT_JUDGE_MODEL,
        strict: bool = True,
    ):
        self.judge_llm = judge_llm
        self.judge_model_name = judge_model_name
        self.strict = strict

    def _get_judge_llm(self) -> Any:
        if self.judge_llm is None:
            self.judge_llm = init_chat_model(model=self.judge_model_name, temperature=0.0)
        return self.judge_llm

    @staticmethod
    def _build_trajectory_prompt(
        user_query: str,
        target_tools: List[str],
        trajectory: List[Dict[str, Any]],
        final_answer: str,
    ) -> str:
        steps = [
            {
                "step": i,
                "tool": t.get("tool_name"),
                "arguments": t.get("arguments"),
                "status": t.get("status", "ok"),
                "result_excerpt": t.get("result_preview", t.get("response_snippet", "")),
            }
            for i, t in enumerate(trajectory, 1)
        ]
        traj_str = json.dumps(steps, ensure_ascii=False, indent=2)
        return (
            f"당신은 AI 에이전트의 도구 호출 과정(Tool Trajectory)을 감사하는 수석 평가자입니다.\n\n"
            f"[사용자 요청]: {user_query}\n"
            f"[기대/권장 도구]: {target_tools}\n"
            f"[실행된 도구 호출 {len(steps)}회]:\n{traj_str}\n\n"
            f"[에이전트 최종 답변]:\n{final_answer}\n\n"
            f"평가 시 유의사항:\n"
            f"- 권장 도구는 기준일 뿐입니다. 권장 도구를 포함하고 과업에 도움 되는 보조 도구(예: glob_search로 경로 확인)를 적절히 쓴 것은 감점하지 마세요.\n"
            f"- 권장 도구 중 'A | B'처럼 묶인 항목은 대체 가능한 도구입니다. 둘 중 하나만 써도 권장 도구를 쓴 것으로 인정합니다.\n"
            f"- 단, 대상 폴더/파일이 없음을 이미 확인했는데도 프로젝트 전체를 훑는 등 헛도는 과잉 탐색(예: 불필요한 glob/grep 연쇄 4회 이상)은 `step_economy_score`에서 엄격히 감점하세요.\n"
            f"- 도구 오류(`status='error'`)가 발생했을 때 원인을 파악해 대안 파일/도구로 복구했다면 정상 대응이므로 `error_recovery_score`를 1.0으로 채점하세요. 같은 실패를 반복하거나 복구하지 못하면 감점하세요. 오류가 전혀 없이 매끄럽게 완료된 경우에도 `error_recovery_score=1.0`입니다.\n\n"
            f"먼저 `critique`에 호출 흐름, 과잉 탐색 여부, 오류 복구 여부를 2~3문장으로 적으세요.\n"
            f"그다음 4개 지표를 0.0~1.0 점수로 채점하세요 (기준: 1.0 문제 없음 / 0.7 사소한 비효율 / 0.4 명확한 문제 / 0.0 실패):\n"
            f"1. tool_selection_accuracy\n"
            f"2. argument_quality_score\n"
            f"3. step_economy_score\n"
            f"4. error_recovery_score"
        )

    @staticmethod
    def _build_outcome_prompt(
        user_query: str,
        ground_truth: str,
        contexts: List[str],
        final_answer: str,
    ) -> str:
        context_str = "\n---\n".join(contexts) if contexts else "[도구 관측 결과 없음]"
        return (
            f"당신은 AI 에이전트의 최종 답변 품질을 감사하는 수석 심판관입니다.\n\n"
            f"[사용자 요청]: {user_query}\n"
            f"[Ground Truth 기준 정답]: {ground_truth}\n"
            f"[도구 실행 관측 결과 (Contexts)]:\n{context_str}\n\n"
            f"[에이전트 최종 답변]:\n{final_answer}\n\n"
            f"먼저 `rationale`에 Ground Truth의 핵심 사실(수치, 파일명, 심볼, 계산, 결론)을 답변과 하나씩 대조하고, 답변 내용이 Contexts에 근거하는지 3~5문장으로 적으세요.\n"
            f"그다음 3개 지표를 0.0~1.0 점수로 채점하세요 (기준: 1.0 완전 / 0.7 사소한 누락·차이 1개 / 0.4 핵심 사실 일부 틀림·누락 / 0.0 완전히 틀리거나 환각):\n"
            f"1. task_completion: 답변의 핵심 수치·항목·결론이 Ground Truth와 일치하는가? (표현 차이는 감점하지 않음. Ground Truth가 '미존재 안내'를 요구할 때 확인되지 않는다고 답하면 1.0, 없는 수치나 가격을 지어내면 0.0)\n"
            f"2. factual_grounding: 답변의 모든 주장과 수치가 [도구 실행 관측 결과]에 실제로 근거하는가? (도구 결과에 없는 내용을 지어내면 감점, 정당한 미존재 안내는 1.0)\n"
            f"3. answer_relevance: 답변이 사용자 질문과 요구 형식에 직접적이고 명확하게 답하는가?"
        )

    def evaluate_trajectory(
        self,
        user_query: str,
        target_tools: List[str],
        trajectory: List[Dict[str, Any]],
        final_answer: str,
    ) -> TrajectoryEvaluation:
        prompt = self._build_trajectory_prompt(user_query, target_tools, trajectory, final_answer)
        try:
            structured = self._get_judge_llm().with_structured_output(TrajectoryEvaluation)
            raw = structured.invoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["exclude_from_stream"]},
            )
            return _coerce_model(raw, TrajectoryEvaluation)
        except Exception as e:
            if self.strict:
                raise
            return TrajectoryEvaluation(
                critique=f"Trajectory evaluation fallback: {e}",
                tool_selection_accuracy=0.8,
                argument_quality_score=0.8,
                step_economy_score=0.8,
                error_recovery_score=0.8,
            )

    async def aevaluate_trajectory(
        self,
        user_query: str,
        target_tools: List[str],
        trajectory: List[Dict[str, Any]],
        final_answer: str,
    ) -> TrajectoryEvaluation:
        prompt = self._build_trajectory_prompt(user_query, target_tools, trajectory, final_answer)
        try:
            structured = self._get_judge_llm().with_structured_output(TrajectoryEvaluation)
            raw = await structured.ainvoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["exclude_from_stream"]},
            )
            return _coerce_model(raw, TrajectoryEvaluation)
        except Exception as e:
            if self.strict:
                raise
            return TrajectoryEvaluation(
                critique=f"Trajectory evaluation fallback: {e}",
                tool_selection_accuracy=0.8,
                argument_quality_score=0.8,
                step_economy_score=0.8,
                error_recovery_score=0.8,
            )

    def evaluate_outcome(
        self,
        user_query: str,
        ground_truth: str,
        contexts: List[str],
        final_answer: str,
    ) -> OutcomeEvaluation:
        prompt = self._build_outcome_prompt(user_query, ground_truth, contexts, final_answer)
        try:
            structured = self._get_judge_llm().with_structured_output(OutcomeEvaluation)
            raw = structured.invoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["exclude_from_stream"]},
            )
            return _coerce_model(raw, OutcomeEvaluation)
        except Exception as e:
            if self.strict:
                raise
            return OutcomeEvaluation(
                rationale=f"Outcome evaluation fallback: {e}",
                task_completion=0.8,
                factual_grounding=0.8,
                answer_relevance=0.8,
            )

    async def aevaluate_outcome(
        self,
        user_query: str,
        ground_truth: str,
        contexts: List[str],
        final_answer: str,
    ) -> OutcomeEvaluation:
        prompt = self._build_outcome_prompt(user_query, ground_truth, contexts, final_answer)
        try:
            structured = self._get_judge_llm().with_structured_output(OutcomeEvaluation)
            raw = await structured.ainvoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["exclude_from_stream"]},
            )
            return _coerce_model(raw, OutcomeEvaluation)
        except Exception as e:
            if self.strict:
                raise
            return OutcomeEvaluation(
                rationale=f"Outcome evaluation fallback: {e}",
                task_completion=0.8,
                factual_grounding=0.8,
                answer_relevance=0.8,
            )
