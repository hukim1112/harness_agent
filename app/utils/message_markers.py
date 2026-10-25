"""
하네스가 대화(state["messages"])에 직접 넣는 메시지의 출처 표식과 "사용자 턴 경계" 판별 규칙.

압축 요약·자가 수정 피드백은 모두 HumanMessage로 대화에 들어갑니다.
그래서 "HumanMessage = 새 사용자 턴"으로 가정하면 턴을 잘못 셉니다. 턴 경계가 필요한
모든 미들웨어(Summarization, StopHooks, Memory, PromptAssembler)는 이 모듈의 함수만 사용합니다.

규칙:
1. 하네스가 만든 메시지는 additional_kwargs["harness_origin"]에 출처를 기록합니다.
   - compaction_summary : 요약 미들웨어가 만든 이전 대화 요약
   - stop_hook_feedback : StopHooks가 넣은 코드 검증 실패 피드백
2. 사용자 턴의 시작 = 출처 표식이 없는 HumanMessage.
3. LangChain SummarizationMiddleware를 하위 클래스 없이 쓴 경우의 요약(lc_source="summarization")도
   compaction_summary로 봅니다.
"""

from typing import Any, Dict, List, Optional, Sequence

from langchain_core.messages import HumanMessage

ORIGIN_KEY = "harness_origin"
ORIGIN_COMPACTION_SUMMARY = "compaction_summary"
ORIGIN_STOP_HOOK = "stop_hook_feedback"

# 원문 저장소(transcript.db)에 기록하지 않을 메시지 표식 (압축 요약은 record_compaction()으로 따로 기록)
TRANSCRIPT_SKIP_KEY = "transcript_skip"

# 모델이 읽는 머리말: 사람이 보낸 요청이 아니라는 점을 메시지 첫 줄에서 분명히 밝힙니다.
COMPACTION_SUMMARY_HEADER = "[Compaction Summary: Previous Conversation]"
STOP_HOOK_TAG = "[stop_hook_blocking]"
AUTO_GENERATED_NOTE = (
    "(This message was generated automatically by the agent harness. "
    "It is NOT a new request from the user.)"
)


def origin_kwargs(origin: str) -> Dict[str, Any]:
    """하네스 생성 메시지에 붙일 additional_kwargs를 만듭니다."""
    kwargs: Dict[str, Any] = {ORIGIN_KEY: origin}
    if origin == ORIGIN_COMPACTION_SUMMARY:
        kwargs[TRANSCRIPT_SKIP_KEY] = True
    return kwargs


def _kwargs(msg: Any) -> Dict[str, Any]:
    if isinstance(msg, dict):
        value = msg.get("additional_kwargs") or {}
    else:
        value = getattr(msg, "additional_kwargs", None) or {}
    return value if isinstance(value, dict) else {}


def _text(msg: Any) -> str:
    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [c.get("text", "") if isinstance(c, dict) else str(c) for c in content]
        return "\n".join(p for p in parts if p)
    return str(content or "")


def _is_human(msg: Any) -> bool:
    if isinstance(msg, HumanMessage):
        return True
    if isinstance(msg, dict):
        return str(msg.get("role") or msg.get("type") or "").lower() in ("human", "user")
    return getattr(msg, "type", None) == "human"


def message_origin(msg: Any) -> Optional[str]:
    """하네스가 만든 메시지면 출처를, 사용자·모델·도구가 만든 메시지면 None을 반환합니다."""
    kwargs = _kwargs(msg)
    origin = kwargs.get(ORIGIN_KEY)
    if origin:
        return str(origin)
    if kwargs.get("lc_source") == "summarization":
        return ORIGIN_COMPACTION_SUMMARY
    if STOP_HOOK_TAG in _text(msg).lstrip()[:60]:
        return ORIGIN_STOP_HOOK
    return None


def is_compaction_artifact(msg: Any) -> bool:
    """압축 단계가 만든 메시지(이전 대화 요약)인지."""
    return message_origin(msg) == ORIGIN_COMPACTION_SUMMARY


def is_compaction_summary(msg: Any) -> bool:
    return message_origin(msg) == ORIGIN_COMPACTION_SUMMARY


def is_stop_hook_feedback(msg: Any) -> bool:
    return _is_human(msg) and message_origin(msg) == ORIGIN_STOP_HOOK


def is_user_turn_start(msg: Any) -> bool:
    """실제 사용자 턴의 시작 메시지인지 (출처 표식이 없는 HumanMessage)."""
    return _is_human(msg) and message_origin(msg) is None


def user_turn_starts(messages: Sequence[Any]) -> List[int]:
    """사용자 턴이 시작되는 메시지 인덱스 목록."""
    return [i for i, m in enumerate(messages) if is_user_turn_start(m)]


def last_user_turn_start(messages: Sequence[Any]) -> Optional[int]:
    """마지막(현재) 사용자 턴이 시작되는 인덱스. 없으면 None."""
    for i in range(len(messages) - 1, -1, -1):
        if is_user_turn_start(messages[i]):
            return i
    return None
