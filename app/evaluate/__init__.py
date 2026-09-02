"""
===============================================================================
[Evaluation Module] Offline Benchmark & Optimization Engine
===============================================================================
Source: app/evaluate/__init__.py

에이전트 공학 EDD(Evaluation-Driven Development)의 오프라인 평가 및 최적화 엔진.
- benchmark: Linter + LLM-as-a-Judge 2단계 배치 평가 파이프라인
- optimizer: 힐 클라이밍(Hill Climbing) 기반 프롬프트 자동 진화 및 Early Stopping
===============================================================================
"""

from app.evaluate.optimizer import (
    evaluate_system_prompt,
    hill_climbing_optimize,
    DEFAULT_PROPOSER_SYSTEM_PROMPT,
)

__all__ = [
    "evaluate_system_prompt",
    "hill_climbing_optimize",
    "DEFAULT_PROPOSER_SYSTEM_PROMPT",
]
