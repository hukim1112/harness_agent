# ===============================================================================
# Compaction Middleware Package
# ===============================================================================
# 컨텍스트 윈도우 압축 미들웨어 (2단):
# - ToolResultSwapMiddleware      : 큰 도구 결과를 생성 즉시 디스크로 swap (미리보기 + 경로)
# - HarnessSummarizationMiddleware: LangChain prebuilt SummarizationMiddleware + 하네스 연동
# create_compaction_middleware()가 두 미들웨어를 권장 설정으로 묶어 반환합니다.
# ===============================================================================

from typing import Any, List, Optional

from .summarization import HarnessSummarizationMiddleware
from .tool_result_swap import (
    DEFAULT_MAX_RESULT_CHARS,
    DEFAULT_PREVIEW_CHARS,
    ToolResultSwapMiddleware,
)


def create_compaction_middleware(
    llm: Any,
    trigger_tokens: int = 8000,
    keep_tokens: int = 3000,
    swap_dir: Optional[str] = None,
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS,
    preview_chars: int = DEFAULT_PREVIEW_CHARS,
    transcript_store: Optional[Any] = None,
    summary_llm: Optional[Any] = None,
    summary_prompt: Optional[str] = None,
) -> List[Any]:
    """[ToolResultSwapMiddleware, HarnessSummarizationMiddleware]를 반환합니다.

    create_agent(middleware=[..., *create_compaction_middleware(llm)])처럼 펼쳐서 넣습니다.
    - trigger_tokens: 대화 추정 토큰 또는 직전 모델 호출의 실사용 토큰이 이 값 이상이면 요약합니다.
    - keep_tokens   : 요약 후 원문 그대로 남길 최근 메시지 분량(토큰).
    - swap_dir      : 없으면 artifacts/users/{user_id}/sessions/{session_id}/tool-results/에 저장합니다.
    - summary_llm   : 요약에 쓸 모델 (없으면 llm).
    - summary_prompt: 요약 지시문 ({messages} 자리표시자 필수). 없으면 LangChain 기본 프롬프트.
    """
    summary_kwargs = {"summary_prompt": summary_prompt} if summary_prompt else {}
    return [
        ToolResultSwapMiddleware(
            swap_dir=swap_dir,
            max_result_chars=max_result_chars,
            preview_chars=preview_chars,
        ),
        HarnessSummarizationMiddleware(
            summary_llm or llm,
            trigger=("tokens", trigger_tokens),
            keep=("tokens", keep_tokens),
            trim_tokens_to_summarize=None,
            transcript_store=transcript_store,
            **summary_kwargs,
        ),
    ]


__all__ = [
    "ToolResultSwapMiddleware",
    "HarnessSummarizationMiddleware",
    "create_compaction_middleware",
]
