"""
===============================================================================
[H-01b] Summarization (LangChain prebuilt SummarizationMiddleware + 하네스 연동)
===============================================================================
요약 로직은 langchain.agents.middleware.SummarizationMiddleware를 그대로 씁니다.
  - before_model에서 대화 토큰이 trigger를 넘으면, 최근 keep 분량만 남기고 앞부분을 LLM으로 요약해
    state["messages"]를 [요약 + 최근 메시지]로 교체합니다.
  - 자르는 지점은 AIMessage(tool_calls)와 ToolMessage 쌍이 갈라지지 않도록 조정됩니다.
  - 요약 호출이 실패하면 3회 재시도 후 에러를 그대로 올립니다 (가짜 요약으로 대화를 덮지 않음).

이 하위 클래스는 하네스 연동 세 가지만 덧붙입니다.
  1. 요약 메시지에 harness_origin 표식과 머리말을 붙입니다. 표식이 없으면 message_markers가
     요약을 "새 사용자 턴"으로 세어 StopHooks·Memory가 턴을 잘못 판별합니다.
  2. 요약 호출에 exclude_from_stream 태그를 붙입니다. 서버(astream_events)가 요약 토큰을
     답변으로 사용자에게 흘려보내지 않게 하기 위해서입니다.
  3. transcript_store가 있으면 압축 이벤트(kind=compaction)를 기록합니다. 원문 전체는
     MemoryMiddleware가 transcript.db에 따로 보존합니다.

prebuilt 기본값에서 주의할 점 (create_compaction_middleware가 바꿔 둔 값):
  - trigger 기본값은 None이라 그대로 두면 요약이 일어나지 않습니다.
  - keep 기본값은 ("messages", 20)이라 큰 메시지가 남으면 압축 효과가 없습니다 → 토큰 기준 사용.
  - trim_tokens_to_summarize 기본값 4000은 요약 대상 중 마지막 4,000토큰만 요약 LLM에 넘겨
    오래된 내용(첫 요청 등)이 요약에서 빠집니다 → None. 요약 대상은 trigger 크기를 넘지 않으므로
    trigger를 요약 모델의 컨텍스트보다 작게 두면 안전합니다.
  - trigger는 (1) state["messages"]의 추정 토큰 수, (2) 직전 모델 호출이 보고한 실제 사용량
    (AIMessage.usage_metadata["total_tokens"]) 중 하나라도 넘으면 발동합니다. (2)에는 PromptAssembler가
    붙이는 시스템 프롬프트와 도구 스키마가 포함되므로, trigger는 시스템 프롬프트 크기보다 넉넉히 커야 합니다.
    (keep의 cutoff 계산은 대화 메시지 추정치만 씁니다.)
===============================================================================
"""

import asyncio
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, RemoveMessage
from langchain.agents.middleware import SummarizationMiddleware

from app.utils.message_markers import (
    AUTO_GENERATED_NOTE,
    COMPACTION_SUMMARY_HEADER,
    ORIGIN_COMPACTION_SUMMARY,
    is_compaction_artifact,
    origin_kwargs,
)


class HarnessSummarizationMiddleware(SummarizationMiddleware):
    """SummarizationMiddleware에 하네스 메시지 표식·스트림 숨김·transcript 기록을 더한 버전."""

    def __init__(self, model: Any, *, transcript_store: Optional[Any] = None, **kwargs: Any):
        super().__init__(model, **kwargs)
        self._summary_model = self.model.with_config(tags=["exclude_from_stream"]).with_retry()
        self.transcript_store = transcript_store

    @staticmethod
    def _build_new_messages(summary: str) -> list[HumanMessage]:
        return [
            HumanMessage(
                content=(f"{COMPACTION_SUMMARY_HEADER}\n{AUTO_GENERATED_NOTE}\n\n"
                         f"Here is a summary of the conversation to date:\n\n{summary}"),
                additional_kwargs={"lc_source": "summarization", **origin_kwargs(ORIGIN_COMPACTION_SUMMARY)},
            )
        ]

    def before_model(self, state, runtime) -> Optional[Dict[str, Any]]:
        update = super().before_model(state, runtime)
        if update:
            self._record_compaction(runtime, state["messages"], update["messages"])
        return update

    async def abefore_model(self, state, runtime) -> Optional[Dict[str, Any]]:
        update = await super().abefore_model(state, runtime)
        if update:
            await asyncio.to_thread(self._record_compaction, runtime, state["messages"], update["messages"])
        return update

    def _record_compaction(self, runtime: Any, original: list, new_messages: list) -> None:
        if self.transcript_store is None:
            return
        ctx = getattr(runtime, "context", None)
        if ctx is not None and not getattr(ctx, "transcript_enabled", True):
            return
        session_id = getattr(ctx, "session_id", "unknown") if ctx else "unknown"
        user_id = getattr(ctx, "user_id", "default") if ctx else "default"
        if session_id == "unknown":
            cfg = getattr(runtime, "config", None)
            if isinstance(cfg, dict):
                session_id = str((cfg.get("configurable") or {}).get("thread_id") or "unknown")
        if session_id == "unknown":
            return
        kept = [m for m in new_messages if not isinstance(m, RemoveMessage)]
        summary = next((str(m.content) for m in kept if is_compaction_artifact(m)), "")
        kept_ids = {m.id for m in kept if getattr(m, "id", None)}
        compacted_uids = [str(m.id) for m in original
                          if getattr(m, "id", None) and m.id not in kept_ids and not is_compaction_artifact(m)]
        try:
            self.transcript_store.record_compaction(
                session_id=session_id,
                user_id=user_id,
                summary=summary,
                compacted_uids=compacted_uids,
                replaced_count=len(original),
            )
        except Exception:
            pass
