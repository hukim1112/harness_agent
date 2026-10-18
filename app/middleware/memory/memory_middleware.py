"""
===============================================================================
Memory Middleware — AgentMiddleware (before_agent + after_agent + get_tools)
===============================================================================
Source: frontier-agent-lab/modules/hermes/memory_middleware.py
        + memory_tool.py + session_search_tool.py (도구 통합)

고응집 메모리 미들웨어 — 스토어, 도구, 훅을 모두 소유합니다.

Hooks:
- before_agent / abefore_agent: L2(에피소드) 자동 인출 + L3(시맨틱) 프리페치 → recalled_memory 주입
- after_agent / aafter_agent: 비동기 스레드 풀로 Background Review 실행
  (메모리 학습 활성화 시 MEMORY.md/USER.md 갱신 및 episodic.db 저장·요약)

Tool Factory:
- self.tools: [memory(), session_recall()] 도구를 소유하며, create_agent()가 생성 시 자동으로 에이전트 도구로 주입
  - memory(): 에이전트가 직접 MEMORY.md / USER.md를 관리 (add/replace/remove)
  - session_recall(): Anchor 기반 과거 세션 상세 메시지 인출
  - session_search는 도구로 제공하지 않음 (before_agent가 자동 인출)

Background Review (Hermes _spawn_background_review 패턴):
- 메인 스레드를 블로킹하지 않음 (ThreadPoolExecutor + 세션별 cancel_event 취소 제어)
- 별도 LLM 호출로 대화 리뷰 → memory(add/replace) 파싱 실행
- EpisodicStore에 세션 요약 저장
===============================================================================
"""

import re
import json
import time
import logging
import asyncio
import threading
import concurrent.futures
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage, ToolMessage
from langchain.tools import tool as langchain_tool
from app.utils.message_utils import normalize_content
from app.middleware.memory.semantic_store import SemanticMemoryStore

logger = logging.getLogger(__name__)

_DEFAULT_USER_ID = "default"
_memory_user_id_var: ContextVar[str] = ContextVar("_memory_user_id_var", default=_DEFAULT_USER_ID)

# ── Background Review Prompts ──

COMBINED_REVIEW_PROMPT = """Review the conversation above and update two things:

**Memory** — who the user is.
Did the user reveal personal information, preferences, communication style, or workflow habits?
If so, save them using: memory(action="add", target="user", content="...")
Write entries in concise English. Keep each entry to 1-2 sentences.

**Agent Notes** — what you learned.
Did you discover new environment facts, project conventions, tool quirks, or useful patterns?
If so, save them using: memory(action="add", target="memory", content="...")
Write entries in concise English. Keep each entry to 1-2 sentences.

IMPORTANT:
- Only save genuinely NEW or UPDATED information. Check existing entries first.
- Do NOT save task-specific data, logs, conversation summaries, or temporary state.
- If nothing is worth saving, respond with "Nothing to save."
- Merge overlapping entries using memory(action="replace", target=..., old_text=..., content=...).

Current MEMORY.md entries:
{memory_entries}

Current USER.md entries:
{user_entries}
"""


def _serialize_message_for_review(msg) -> Dict[str, str]:
    """메시지를 리뷰용 텍스트로 직렬화."""
    if isinstance(msg, BaseMessage):
        return {"role": msg.type, "content": msg.content or ""}
    if isinstance(msg, dict):
        return {
            "role": msg.get("role", msg.get("type", "unknown")),
            "content": msg.get("content", ""),
        }
    return {"role": "unknown", "content": str(msg)}


def _sanitize_user_id(user_id: Optional[str]) -> str:
    from app.utils.workspace import sanitize_path_segment
    return sanitize_path_segment(user_id, fallback=_DEFAULT_USER_ID)


class MemoryMiddleware(AgentMiddleware):
    """고응집 메모리 미들웨어 — 스토어, 도구, 훅을 모두 소유.

    Usage:
        memory_mw = MemoryMiddleware(
            semantic_store=semantic_store,
            episodic_store=episodic_store,
            review_llm=llm,
        )
        agent = create_agent(
            model=llm,
            tools=base_tools,          # memory_mw.tools는 create_agent가 자동 등록
            middleware=[memory_mw],
        )
    """

    def __init__(
        self,
        semantic_store: SemanticMemoryStore,
        episodic_store,
        review_llm=None,
        top_k: int = 2,
    ):
        """
        Args:
            semantic_store: 기본 사용자(default)의 SemanticMemoryStore
            episodic_store: 공유 EpisodicStore (user_id 컬럼으로 사용자 격리)
            review_llm: Background Review(시맨틱 갱신·세션 요약)에 사용할 LLM
            top_k: 매 턴 Layer 4에 자동 주입할 과거 세션(Episodic) 요약 개수
        """
        self.semantic_store = semantic_store
        self.episodic_store = episodic_store
        self.review_llm = review_llm
        self.top_k = max(0, int(top_k))

        from pathlib import Path
        from app.utils.workspace import USERS_BASE_DIR, resolve_user_memory_dir

        default_unified_mem_dir = resolve_user_memory_dir(_DEFAULT_USER_ID, ensure_exists=False).resolve()
        base_sem_dir = Path(semantic_store.memory_dir).resolve()
        self._use_unified_workspace = (
            base_sem_dir == default_unified_mem_dir
            or base_sem_dir == USERS_BASE_DIR.resolve()
        )

        # 사용자(user_id)별 SemanticMemoryStore 및 마지막 로드된 세션 ID 캐시
        # (EpisodicStore는 app/database/episodic.db 단일 DB를 공유하며 user_id 컬럼으로 격리)
        self._store_lock = threading.RLock()
        self._user_semantic_stores: Dict[str, SemanticMemoryStore] = {
            _DEFAULT_USER_ID: semantic_store
        }
        self._loaded_session_by_user: Dict[str, str] = {}

        # Background Review 제어 (세션별 중복 실행 방지 & 취소 제어 + 스레드 풀 제한)
        self._review_meta_lock = threading.Lock()
        self._review_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="memory-bg-review"
        )
        self._review_cancel_events: Dict[str, threading.Event] = {}
        self._review_futures: Dict[str, concurrent.futures.Future] = {}
        self._session_review_locks: Dict[str, threading.Lock] = {}

        # 내부에서 도구 생성 (스토어 바인딩을 미들웨어가 소유)
        self._memory_tool = self._create_memory_tool()
        self._session_recall_tool = self._create_session_recall_tool()
        # AgentMiddleware.tools — LangChain create_agent()가 생성 시 한 번 읽어 에이전트 도구로 자동 주입합니다
        # (langchain/agents/factory.py의 middleware_tools 수집 → tools=와 합쳐 등록).
        self.tools = [self._memory_tool, self._session_recall_tool]

    def get_tools(self) -> list:
        """메모리 도구 목록 반환 (create_agent 사용 시에는 self.tools를 통해 자동 등록됨).

        Returns:
            [memory_tool, session_recall_tool]
        """
        return [self._memory_tool, self._session_recall_tool]

    def _get_semantic_store(self, user_id: Optional[str] = None) -> SemanticMemoryStore:
        """user_id에 해당하는 SemanticMemoryStore를 반환합니다.
        - 통합 사용자 워크스페이스 모드인 경우: resolve_user_memory_dir(uid) 단일 진실 공급원(SSOT)을 사용
        - 단위 테스트 등에서 임시 디렉터리(sem_root)를 주입한 경우:
          'default'는 기본 스토어를 그대로 사용하고, 그 외 사용자는 {sem_root}/users/{user_id}/memory/ 사용
        """
        from app.utils.workspace import resolve_user_memory_dir

        uid = _sanitize_user_id(user_id or _memory_user_id_var.get())
        with self._store_lock:
            if uid in self._user_semantic_stores:
                return self._user_semantic_stores[uid]

            if self._use_unified_workspace:
                user_dir = resolve_user_memory_dir(uid, ensure_exists=True)
            else:
                user_dir = self.semantic_store.memory_dir / "users" / uid / "memory"

            user_store = SemanticMemoryStore(
                memory_dir=str(user_dir),
                memory_char_limit=self.semantic_store.memory_char_limit,
                user_char_limit=self.semantic_store.user_char_limit,
            )
            user_store.load_from_disk()
            self._user_semantic_stores[uid] = user_store
            return user_store

    def _get_episodic_store(self, user_id: Optional[str] = None):
        """단일 EpisodicStore 인스턴스(app/database/episodic.db)를 반환합니다 (내부 user_id 컬럼으로 격리)."""
        return self.episodic_store

    def _resolve_current_user_id(self, runtime: Any = None) -> str:
        """runtime.context 또는 runnable config 또는 ContextVar에서 현재 user_id를 추출합니다."""
        if runtime is not None:
            ctx = getattr(runtime, "context", None)
            if ctx is not None:
                uid = getattr(ctx, "user_id", None)
                if uid and str(uid).strip():
                    return _sanitize_user_id(str(uid))
        try:
            from langchain_core.runnables.config import get_config_from_context
            cfg = get_config_from_context()
            if isinstance(cfg, dict):
                uid = (cfg.get("configurable") or {}).get("user_id")
                if uid and str(uid).strip():
                    return _sanitize_user_id(str(uid))
        except Exception:
            pass
        return _sanitize_user_id(_memory_user_id_var.get())

    def _cancel_active_review(self, session_id: str) -> None:
        """특정 세션의 진행 중인 Background Review가 있으면 취소 신호를 보냅니다."""
        if not session_id or session_id == "unknown":
            return
        with self._review_meta_lock:
            prev_event = self._review_cancel_events.pop(session_id, None)
            if prev_event is not None:
                prev_event.set()
            prev_future = self._review_futures.pop(session_id, None)
            if prev_future is not None and not prev_future.done():
                prev_future.cancel()

    def wait_for_reviews(self, timeout: float = 10.0) -> None:
        """현재 실행 중인 모든 Background Review 완료를 대기합니다 (테스트 검증용)."""
        with self._review_meta_lock:
            futures = list(self._review_futures.values())
        if futures:
            concurrent.futures.wait(futures, timeout=timeout)

    # ══════════════════════════════════════════════════════════════════
    # Tool Factory
    # ══════════════════════════════════════════════════════════════════

    def _create_memory_tool(self):
        """@tool memory(action, target, content, old_text) 생성."""
        mw = self

        @langchain_tool
        def memory(
            action: str,
            target: str = "memory",
            content: str = "",
            old_text: str = "",
        ) -> str:
            """Manage the agent's long-term semantic memory (MEMORY.md / USER.md).

            Two stores:
            - target="memory": Agent's personal notes (environment facts, project conventions, tool quirks).
            - target="user": What the agent knows about the user (preferences, communication style).

            Actions:
            - action="add": Append a new entry. Content must be concise English.
            - action="replace": Find entry containing old_text, replace with content.
            - action="remove": Find entry containing old_text, delete it.

            Guidelines:
            - Write entries in English for search efficiency.
            - Keep entries short (1-2 sentences). Merge overlapping facts.
            - Do NOT store task-specific data, logs, or temporary state.
            - Current MEMORY.md and USER.md contents for the active user are ALREADY preloaded in Layer 4 (Recalled Memory) of your system prompt. Do NOT use file_read, glob_search, or bash_command to search for USER.md or MEMORY.md on disk.

            Args:
                action: "add" | "replace" | "remove"
                target: "memory" (MEMORY.md) | "user" (USER.md)
                content: New entry text (required for add/replace)
                old_text: Unique substring to match existing entry (required for replace/remove)

            Returns:
                JSON string with success status, usage info, and current entry count.
            """
            uid = mw._resolve_current_user_id()
            store = mw._get_semantic_store(uid)
            if action == "add":
                result = store.add(target, content)
            elif action == "replace":
                result = store.replace(target, old_text, content)
            elif action == "remove":
                result = store.remove(target, old_text)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown action '{action}'. Use add, replace, or remove.",
                }
            return json.dumps(result, ensure_ascii=False, indent=2)

        return memory

    def _create_session_recall_tool(self):
        """@tool session_recall(session_id, anchor_message, window) 생성."""
        mw = self

        def _format_recall_result(
            session_id: str, anchor_message: str, messages: List[Dict[str, Any]]
        ) -> str:
            if not messages:
                return json.dumps({
                    "session_id": session_id,
                    "messages": [],
                    "message": f"No messages found for session '{session_id}'.",
                })
            return json.dumps({
                "session_id": session_id,
                "anchor": anchor_message or "(tail view)",
                "message_count": len(messages),
                "messages": [
                    {"role": m["role"], "content": m["content"][:500]}
                    for m in messages
                ],
            }, ensure_ascii=False, indent=2)

        @langchain_tool
        def session_recall(
            session_id: str,
            anchor_message: str = "",
            window: int = 5,
        ) -> str:
            """Recall messages from a specific past session using anchor-based retrieval.

            Anchor-based retrieval (Hermes Lineage pattern):
            1. Verifies that the target session belongs to the current user (user_id isolation)
            2. Finds the message best matching anchor_message keywords
            3. Returns ±window messages around the anchor
            4. Always includes bookends (first 3 + last 3 messages of the session)

            If anchor_message is empty, returns the last `window` messages of the session.

            Use this tool after seeing a relevant session hint in Recalled Episodic Memory (Layer 4).

            Args:
                session_id: The session ID to recall messages from
                anchor_message: Keywords to locate the most relevant message (optional)
                window: Number of messages before/after the anchor (default 5)

            Returns:
                JSON with messages: [{role, content}, ...]
            """
            uid = mw._resolve_current_user_id()
            epi_store = mw._get_episodic_store(uid)
            messages = _run_async_safe(
                epi_store.get_anchored_view(
                    session_id=session_id,
                    anchor_keyword=anchor_message,
                    window=window,
                    user_id=uid,
                )
            )
            return _format_recall_result(session_id, anchor_message, messages)

        async def _asession_recall(
            session_id: str,
            anchor_message: str = "",
            window: int = 5,
        ) -> str:
            uid = mw._resolve_current_user_id()
            epi_store = mw._get_episodic_store(uid)
            messages = await epi_store.get_anchored_view(
                session_id=session_id,
                anchor_keyword=anchor_message,
                window=window,
                user_id=uid,
            )
            return _format_recall_result(session_id, anchor_message, messages)

        session_recall.coroutine = _asession_recall
        return session_recall

    # ══════════════════════════════════════════════════════════════════
    # 도구 컨텍스트 전파 및 게이팅
    # ══════════════════════════════════════════════════════════════════

    def _disabled_tool_names(self, runtime: Any) -> set:
        """명시적으로 꺼진 메모리 기능의 도구 이름."""
        ctx = getattr(runtime, "context", None)
        if not ctx:
            return set()
        disabled = set()
        if not getattr(ctx, "semantic_memory_enabled", True):
            disabled.add(self._memory_tool.name)
        if not getattr(ctx, "episodic_memory_enabled", True):
            disabled.add(self._session_recall_tool.name)
        return disabled

    def _filter_tools(self, request):
        disabled = self._disabled_tool_names(request.runtime)
        if not disabled:
            return request
        tools = [t for t in request.tools if getattr(t, "name", None) not in disabled]
        return request.override(tools=tools)

    def wrap_model_call(self, request, handler):
        return handler(self._filter_tools(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._filter_tools(request))

    def _blocked_tool_message(self, request) -> Optional[ToolMessage]:
        name = request.tool_call.get("name")
        if name not in self._disabled_tool_names(request.runtime):
            return None
        return ToolMessage(
            content=f"'{name}' 도구는 현재 대화에서 메모리 기능이 꺼져 있어 사용할 수 없습니다.",
            tool_call_id=request.tool_call.get("id", ""),
            name=name,
            status="error",
        )

    def wrap_tool_call(self, request, handler):
        blocked = self._blocked_tool_message(request)
        if blocked:
            return blocked
        uid = self._resolve_current_user_id(getattr(request, "runtime", None))
        tok = _memory_user_id_var.set(uid)
        try:
            return handler(request)
        finally:
            _memory_user_id_var.reset(tok)

    async def awrap_tool_call(self, request, handler):
        blocked = self._blocked_tool_message(request)
        if blocked:
            return blocked
        uid = self._resolve_current_user_id(getattr(request, "runtime", None))
        tok = _memory_user_id_var.set(uid)
        try:
            return await handler(request)
        finally:
            _memory_user_id_var.reset(tok)

    # ══════════════════════════════════════════════════════════════════
    # AgentMiddleware Hooks
    # ══════════════════════════════════════════════════════════════════

    def _prepare_turn_and_semantic_memory(
        self, runtime: Any
    ) -> Optional[tuple[Any, str, str, List[str]]]:
        """턴 시작 시 session_id/user_id를 해석하고, 이전 리뷰 취소 및 L3 Semantic Memory 프리페치를 수행합니다."""
        ctx = getattr(runtime, "context", None)
        if not ctx:
            return None

        session_id = self._get_session_id(runtime)
        if session_id != "unknown":
            ctx.session_id = session_id

        user_id = self._resolve_current_user_id(runtime)
        _memory_user_id_var.set(user_id)

        # 같은 세션에서 새 턴이 시작되면 진행 중이던 이전 턴 Background Review를 즉시 취소
        self._cancel_active_review(session_id)

        recalled_parts: List[str] = []

        # L3: Semantic Memory 프리페치 (세션 감지 기반 Frozen Snapshot, user_id 격리)
        if getattr(ctx, "semantic_memory_enabled", True):
            store = self._get_semantic_store(user_id)
            with self._store_lock:
                # 세션이 전환된 순간에만 디스크에서 최신 마크다운 로드 (세션 내 KV-Cache 보존)
                if self._loaded_session_by_user.get(user_id) != session_id:
                    store.load_from_disk()
                    self._loaded_session_by_user[user_id] = session_id
                    logger.info(
                        "[MemoryMiddleware] New session detected (user=%s, session=%s): reloaded semantic memory snapshot.",
                        user_id, session_id,
                    )

                memory_block = store.format_for_prompt("memory")
                user_block = store.format_for_prompt("user")
                mem_limit = store.memory_char_limit
                usr_limit = store.user_char_limit
            if memory_block:
                recalled_parts.append(memory_block)
            else:
                recalled_parts.append(
                    "══════════════════════════════════════════════\n"
                    f"MEMORY (agent's personal notes) [0% — 0/{mem_limit:,} chars]\n"
                    "══════════════════════════════════════════════\n"
                    "(No entries recorded yet in MEMORY.md for this user.)"
                )
            if user_block:
                recalled_parts.append(user_block)
            else:
                recalled_parts.append(
                    "══════════════════════════════════════════════\n"
                    f"USER PROFILE (who the user is) [0% — 0/{usr_limit:,} chars]\n"
                    "══════════════════════════════════════════════\n"
                    "(No entries recorded yet in USER.md for this user.)"
                )

        return ctx, session_id, user_id, recalled_parts

    def before_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """동기 실행 경로용 L2+L3 메모리 인출 → AgentContext.recalled_memory에 주입."""
        prepared = self._prepare_turn_and_semantic_memory(runtime)
        if not prepared:
            return None
        ctx, session_id, user_id, recalled_parts = prepared

        # L2: Episodic Memory 자동 인출 (동기 호출자용 _run_async_safe 경로)
        if getattr(ctx, "episodic_memory_enabled", True) and self.top_k > 0:
            user_query = self._extract_last_user_query(state)
            if user_query:
                try:
                    epi_store = self._get_episodic_store(user_id)
                    sessions = _run_async_safe(
                        epi_store.search_sessions(
                            user_query,
                            top_k=self.top_k,
                            exclude_session_id=session_id,
                            user_id=user_id,
                        )
                    )
                    if sessions:
                        recalled_parts.append(self._format_episodic(sessions))
                except Exception as e:
                    logger.warning("Episodic memory retrieval failed: %s", e)

        if recalled_parts:
            ctx.recalled_memory = "\n\n".join(recalled_parts)

        return None

    async def abefore_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """비동기 실행 경로(FastAPI ainvoke/astream_events)용 네이티브 논블로킹 L2+L3 메모리 인출."""
        prepared = await asyncio.to_thread(self._prepare_turn_and_semantic_memory, runtime)
        if not prepared:
            return None
        ctx, session_id, user_id, recalled_parts = prepared
        _memory_user_id_var.set(user_id)

        # L2: Episodic Memory 자동 인출 (이벤트 루프를 블로킹하지 않는 네이티브 await 경로)
        if getattr(ctx, "episodic_memory_enabled", True) and self.top_k > 0:
            user_query = self._extract_last_user_query(state)
            if user_query:
                try:
                    epi_store = self._get_episodic_store(user_id)
                    sessions = await epi_store.search_sessions(
                        user_query,
                        top_k=self.top_k,
                        exclude_session_id=session_id,
                        user_id=user_id,
                    )
                    if sessions:
                        recalled_parts.append(self._format_episodic(sessions))
                except Exception as e:
                    logger.warning("Episodic memory retrieval failed: %s", e)

        if recalled_parts:
            ctx.recalled_memory = "\n\n".join(recalled_parts)

        return None

    def after_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """비동기 스레드 풀로 Background Review 실행 (세션별 이전 리뷰 자동 취소).

        Hermes 패턴: 메인 응답에 영향 없이 백그라운드에서 메모리 갱신하되,
        같은 세션의 이전 턴 리뷰가 아직 돌고 있으면 취소하여 옛 요약이 최신 요약을 덮어쓰지 않도록 보장.
        """
        ctx = getattr(runtime, "context", None)
        if not ctx:
            return None

        messages = state.get("messages", [])
        if not messages or len(messages) < 2:
            return None

        base_learning = getattr(ctx, "memory_learning_enabled", True)
        semantic_learning = (
            getattr(ctx, "semantic_memory_enabled", True)
            and bool(base_learning)
            and getattr(ctx, "semantic_learning_enabled", True)
        )
        episodic_learning = (
            getattr(ctx, "episodic_memory_enabled", True)
            and bool(base_learning)
            and getattr(ctx, "episodic_learning_enabled", True)
        )
        if not (semantic_learning or episodic_learning):
            return None

        # 대화 스냅샷 복제
        messages_snapshot = [
            _serialize_message_for_review(m) for m in messages
        ]
        session_id = self._get_session_id(runtime)
        user_id = self._resolve_current_user_id(runtime)

        # 같은 세션의 이전 리뷰가 진행 중이면 취소 신호 발송
        self._cancel_active_review(session_id)

        cancel_event = threading.Event()
        with self._review_meta_lock:
            self._review_cancel_events[session_id] = cancel_event
            self._session_review_locks.setdefault(session_id, threading.Lock())
            future = self._review_executor.submit(
                self._background_review,
                messages_snapshot,
                session_id,
                user_id,
                semantic_learning,
                episodic_learning,
                cancel_event,
            )
            self._review_futures[session_id] = future

        logger.info("Background review scheduled for session %s (user=%s)", session_id, user_id)
        return None

    async def aafter_agent(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        return self.after_agent(state, runtime)

    # ══════════════════════════════════════════════════════════════════
    # Background Review (Bounded ThreadPool + Session Cancel/Lock)
    # ══════════════════════════════════════════════════════════════════

    def _background_review(
        self,
        messages_snapshot: List[Dict[str, str]],
        session_id: str,
        user_id: str = _DEFAULT_USER_ID,
        semantic_learning: bool = True,
        episodic_learning: bool = True,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        """Background Review 워커.

        1. semantic_learning: LLM에게 대화 리뷰 요청 → memory() 호출 파싱 실행
        2. episodic_learning: EpisodicStore에 세션 저장 + 요약
        진행 도중 같은 세션에서 새 턴이 시작되어 cancel_event가 설정되면 즉시 중단합니다.
        """
        if cancel_event is not None and cancel_event.is_set():
            logger.info("[BG-Review] Skipped cancelled review for session %s", session_id)
            return

        with self._review_meta_lock:
            session_lock = self._session_review_locks.setdefault(session_id, threading.Lock())

        try:
            logger.info(
                "[BG-Review] Starting background review for session %s (user=%s, semantic=%s, episodic=%s)",
                session_id, user_id, semantic_learning, episodic_learning,
            )

            # 1. Semantic Memory 갱신 (LLM 리뷰)
            if semantic_learning and self.review_llm:
                if cancel_event is not None and cancel_event.is_set():
                    return
                self._review_semantic_memory(
                    messages_snapshot, user_id=user_id, cancel_event=cancel_event, session_lock=session_lock
                )

            # 2. Episodic Memory 세션 요약 저장
            if episodic_learning:
                if cancel_event is not None and cancel_event.is_set():
                    return
                self._review_episodic_memory(
                    messages_snapshot, session_id, user_id=user_id, cancel_event=cancel_event, session_lock=session_lock
                )

            logger.info("[BG-Review] Completed for session %s", session_id)

        except Exception as e:
            logger.error("[BG-Review] Failed for session %s: %s", session_id, e)

    def _review_semantic_memory(
        self,
        messages: List[Dict[str, str]],
        user_id: str = _DEFAULT_USER_ID,
        cancel_event: Optional[threading.Event] = None,
        session_lock: Optional[threading.Lock] = None,
    ) -> None:
        """LLM으로 대화를 리뷰하여 사용자별 MEMORY.md/USER.md 갱신."""
        if not self.review_llm:
            return
        if cancel_event is not None and cancel_event.is_set():
            return

        store = self._get_semantic_store(user_id)

        # 현재 엔트리를 프롬프트에 포함
        memory_entries = "\n".join(
            f"- {e}" for e in store.memory_entries
        ) or "(empty)"
        user_entries = "\n".join(
            f"- {e}" for e in store.user_entries
        ) or "(empty)"

        # 대화 텍스트 구성
        conversation_text = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in messages
            if m.get("content") and m.get("role") != "tool"
        )

        review_prompt = (
            f"Conversation:\n{conversation_text[:3000]}\n\n"
            + COMBINED_REVIEW_PROMPT.format(
                memory_entries=memory_entries,
                user_entries=user_entries,
            )
        )

        try:
            response = self.review_llm.invoke(review_prompt)
            if cancel_event is not None and cancel_event.is_set():
                logger.info("[BG-Review] Cancelled stale semantic review before applying ops (user=%s)", user_id)
                return

            content = normalize_content(getattr(response, "content", response))

            # LLM 응답에서 memory() 호출 파싱 및 실행 (세션 락 하에서 취소 재확인 후 반영)
            if session_lock is not None:
                with session_lock:
                    if cancel_event is not None and cancel_event.is_set():
                        return
                    self._parse_and_execute_memory_ops(content, store=store)
            else:
                self._parse_and_execute_memory_ops(content, store=store)

        except Exception as e:
            logger.warning("[BG-Review] Semantic review LLM call failed: %s", e)

    def _parse_and_execute_memory_ops(
        self, llm_response: str, store: Optional[SemanticMemoryStore] = None
    ) -> None:
        """LLM 응답에서 memory() 또는 <call:memory ... /> 파싱하여 실행."""
        target_store = store or self.semantic_store

        patterns = [
            r'''memory\(((?:[^)"']|"[^"]*"|'[^']*')*)\)''',
            r'<call:memory\s+([^/>]+)/?>',
            r'<memory\s+([^/>]+)/?>',
        ]

        matches = []
        for p in patterns:
            matches.extend(re.findall(p, llm_response))

        for match in matches:
            try:
                # 인자 파싱
                action = self._extract_kwarg(match, "action")
                target = self._extract_kwarg(match, "target") or "memory"
                content = self._extract_kwarg(match, "content") or ""
                old_text = self._extract_kwarg(match, "old_text") or ""

                if not action:
                    continue

                if action == "add" and content:
                    result = target_store.add(target, content)
                elif action == "replace" and old_text and content:
                    result = target_store.replace(target, old_text, content)
                elif action == "remove" and old_text:
                    result = target_store.remove(target, old_text)
                else:
                    continue

                if result.get("success"):
                    logger.info("[BG-Review] Memory %s: %s → %s",
                                action, target, content[:50] if content else old_text[:50])
                else:
                    logger.warning("[BG-Review] Memory %s failed: %s",
                                   action, result.get("error", "unknown"))

            except Exception as e:
                logger.warning("[BG-Review] Failed to parse memory op '%s': %s", match, e)

    @staticmethod
    def _extract_kwarg(args_str: str, key: str) -> Optional[str]:
        """키워드 인자 문자열에서 특정 키의 값을 추출."""
        pattern = rf'{key}\s*=\s*["\']([^"\']*)["\']'
        m = re.search(pattern, args_str)
        return m.group(1) if m else None

    def _review_episodic_memory(
        self,
        messages: List[Dict[str, str]],
        session_id: str,
        user_id: str = _DEFAULT_USER_ID,
        cancel_event: Optional[threading.Event] = None,
        session_lock: Optional[threading.Lock] = None,
    ) -> None:
        """세션 메시지를 EpisodicStore에 저장 + 요약 생성 (세션 락 및 취소 이벤트 적용)."""
        if cancel_event is not None and cancel_event.is_set():
            return
        epi_store = self._get_episodic_store(user_id)
        try:
            if session_lock is not None:
                with session_lock:
                    if cancel_event is not None and cancel_event.is_set():
                        return
                    _run_async_safe(
                        epi_store.finalize_session(
                            session_id=session_id,
                            messages=messages,
                            llm=self.review_llm,
                            user_id=user_id,
                            cancel_event=cancel_event,
                        )
                    )
            else:
                _run_async_safe(
                    epi_store.finalize_session(
                        session_id=session_id,
                        messages=messages,
                        llm=self.review_llm,
                        user_id=user_id,
                        cancel_event=cancel_event,
                    )
                )
        except Exception as e:
            logger.warning("[BG-Review] Episodic finalize failed: %s", e)

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_last_user_query(state: Dict[str, Any]) -> str:
        """state에서 마지막 유저 메시지 추출."""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, BaseMessage) and msg.type in ("human", "user"):
                return msg.content or ""
            if isinstance(msg, dict) and msg.get("role") in ("human", "user"):
                return msg.get("content", "")
        return ""

    @staticmethod
    def _get_session_id(runtime: Any, request: Any = None) -> str:
        """runtime 및 request에서 session_id(thread_id)를 지능적으로 추출."""
        # 1. langchain_core의 get_config_from_context() 시도
        try:
            from langchain_core.runnables.config import get_config_from_context
            cfg = get_config_from_context()
            if cfg and isinstance(cfg, dict):
                tid = cfg.get("configurable", {}).get("thread_id")
                if tid:
                    return str(tid)
        except Exception:
            pass

        ctx = getattr(runtime, "context", None)
        if not ctx and request:
            ctx = getattr(getattr(request, "runtime", None), "context", None)

        if ctx:
            sid = getattr(ctx, "session_id", None)
            if sid and sid != "unknown":
                return str(sid)

        if request:
            configurable = getattr(request, "configurable", None)
            if isinstance(configurable, dict) and configurable.get("thread_id"):
                return str(configurable["thread_id"])

        config = getattr(runtime, "config", None)
        if not config and request:
            config = getattr(getattr(request, "runtime", None), "config", None)

        if config:
            if isinstance(config, dict):
                tid = config.get("configurable", {}).get("thread_id")
                if tid:
                    return str(tid)
            elif hasattr(config, "get"):
                configurable = config.get("configurable", {})
                if isinstance(configurable, dict) and configurable.get("thread_id"):
                    return str(configurable["thread_id"])
            elif hasattr(config, "configurable"):
                configurable = getattr(config, "configurable", {})
                if isinstance(configurable, dict) and configurable.get("thread_id"):
                    return str(configurable["thread_id"])

        return "unknown"

    @staticmethod
    def _format_episodic(sessions: List[Dict[str, Any]]) -> str:
        """에피소드 검색 결과를 프롬프트 주입용 텍스트로 포맷."""
        if not sessions:
            return ""

        separator = "═" * 46
        header = "EPISODIC MEMORY (relevant past sessions)"
        lines = [separator, header, separator]

        for i, s in enumerate(sessions, 1):
            lines.append(f"[Session {i}] {s.get('session_id', 'unknown')}")
            lines.append(f"  Summary: {s.get('summary', 'N/A')}")
            keywords = s.get("keywords", [])
            if keywords:
                lines.append(f"  Keywords: {', '.join(keywords)}")
            lines.append("")

        return "\n".join(lines)


# ── Module-level helper ──

def _run_async_safe(coro):
    """비동기 코루틴을 안전하게 동기 실행."""
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)
