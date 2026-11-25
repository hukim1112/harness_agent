"""
===============================================================================
[Evaluation Module] Offline Benchmark, Calibration & Optimization Engine
===============================================================================
Source: app/evaluate/__init__.py

에이전트 공학 EDD(Evaluation-Driven Development) 통합 평가 패키지:
- schemas        : CoT-First TrajectoryEvaluation / OutcomeEvaluation / HarnessJudge
- metrics        : 조합 가능한 EvalMetric, EvalSample, PRESET_METRICS, metrics_table
- dataset_builder: 시드 기반 문항 생성·검수(EvalSeed) 및 운영 로그 기반 추출(mine_cases_from_audit_logs)
- runner         : main_agent 오프라인 병렬 평가, pass@k/pass^k, 진단/회귀 비교표, CI 게이트
- optimizer      : Train/Val 분리 + 길이 페널티 기반 프롬프트 힐 클라이밍 최적화
===============================================================================
"""

from typing import TYPE_CHECKING

from app.evaluate.dataset_builder import (
    EvalSeed,
    generate_from_seeds,
    mine_cases_from_audit_logs,
    verify_generated_cases,
)
from app.evaluate.metrics import (
    EvalMetric,
    EvalSample,
    PRESET_METRICS,
    answer_relevance,
    error_recovery,
    factual_grounding,
    metrics_table,
    step_economy,
    task_completion,
    tool_selection,
)
from app.evaluate.optimizer import (
    DEFAULT_PROPOSER_SYSTEM_PROMPT,
    evaluate_system_prompt,
    hill_climbing_optimize,
)
from app.evaluate.schemas import (
    HarnessJudge,
    OUTCOME_WEIGHTS,
    OutcomeEvaluation,
    TRAJECTORY_WEIGHTS,
    TrajectoryEvaluation,
)

if TYPE_CHECKING:
    from app.evaluate.runner import (
        GOLDEN_PATH,
        JUDGE_MODEL,
        NOISE_BAND,
        PASS_THRESHOLD,
        build_main_agent_for_eval,
        compare_reports,
        compare_table,
        diagnosis_table,
        evaluate_agent,
        load_app_agent,
        load_golden,
        results_table,
        run_case,
        save_report,
        summarize,
        summary_line,
    )

_RUNNER_EXPORTS = {
    "GOLDEN_PATH",
    "JUDGE_MODEL",
    "NOISE_BAND",
    "PASS_THRESHOLD",
    "build_main_agent_for_eval",
    "load_app_agent",
    "load_golden",
    "run_case",
    "evaluate_agent",
    "summary_line",
    "results_table",
    "diagnosis_table",
    "summarize",
    "compare_table",
    "save_report",
    "compare_reports",
}


def __getattr__(name: str):
    if name in _RUNNER_EXPORTS:
        from app.evaluate import runner
        return getattr(runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "HarnessJudge",
    "TrajectoryEvaluation",
    "OutcomeEvaluation",
    "TRAJECTORY_WEIGHTS",
    "OUTCOME_WEIGHTS",
    "EvalSeed",
    "generate_from_seeds",
    "verify_generated_cases",
    "mine_cases_from_audit_logs",
    "EvalMetric",
    "EvalSample",
    "PRESET_METRICS",
    "task_completion",
    "factual_grounding",
    "answer_relevance",
    "tool_selection",
    "step_economy",
    "error_recovery",
    "metrics_table",
    "evaluate_system_prompt",
    "hill_climbing_optimize",
    "DEFAULT_PROPOSER_SYSTEM_PROMPT",
    "GOLDEN_PATH",
    "JUDGE_MODEL",
    "NOISE_BAND",
    "PASS_THRESHOLD",
    "build_main_agent_for_eval",
    "load_app_agent",
    "load_golden",
    "run_case",
    "evaluate_agent",
    "summary_line",
    "results_table",
    "diagnosis_table",
    "summarize",
    "compare_table",
    "save_report",
    "compare_reports",
]
