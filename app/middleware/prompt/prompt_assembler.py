"""
===============================================================================
Simplified Prompt Assembler (Claude Code Cache-First Architecture)
===============================================================================
프롬프트 캐싱(Prompt Caching)을 극대화하기 위해 요청 메시지를 4단 구조로 조립합니다:

  ① Tool Specification : API tools 필드 (create_agent 자동 바인딩 + 이름순 정렬)
  ② System Message     : 에이전트 정적 역할 지침(prompt.py)
                         (세션/턴/메모리/스킬/실행지침 비포함 → cache_control: ephemeral)
  ③ User Context       : 대화 맨 앞 <system-reminder> HumanMessage (세션당 1회 동결)
                         # sessionContext · # skillCatalog(지침+초기목록) · # memorySnapshot · # projectRules
  ④ Conversation + Δ   : 대화 메시지 + 대화 끝에 append 되는 <system-reminder> 알림
                         - skill_delta     : 세션 중 추가/제거된 스킬 양방향 Delta
                         - date_change     : 자정 경과 시 날짜 변경 알림
                         (참고: Episodic Memory는 session_search + session_recall 도구로 조회)
===============================================================================
"""

import os
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Union
from typing_extensions import NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.utils.message_markers import (
    ORIGIN_DATE_CHANGE,
    ORIGIN_SKILL_DELTA,
    ORIGIN_USER_CONTEXT,
    is_compaction_artifact,
    message_origin,
    origin_kwargs,
)


# =============================================================================
# Constants & Session LRU Cache
# =============================================================================

MAX_CACHED_SESSIONS = 256
SKILL_DESCRIPTION_MAX_CHARS = 250

SKILL_ADDED_KEY = "skill_added_names"
SKILL_REMOVED_KEY = "skill_removed_names"

WORKSPACE_KEYS = ("workspace_dir", "plan_dir", "scripts_dir", "outputs_dir", "logs_dir")

USER_CONTEXT_INTRO = "As you answer the user's questions, you can use the following context:"
USER_CONTEXT_FOOTER = (
    "IMPORTANT: this context may or may not be relevant to your tasks. "
    "You should not respond to this context unless it is highly relevant to your task."
)


def get_local_iso_date() -> str:
    """로컬 시간 기준 YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


class _SessionLRU(OrderedDict):
    """세션 id → 값. 최근 사용한 MAX_CACHED_SESSIONS개만 유지합니다."""

    def __init__(self, maxsize: int = MAX_CACHED_SESSIONS):
        super().__init__()
        self.maxsize = maxsize

    def get_or_create(self, key: str, factory: Callable[[], Any]) -> Any:
        if key in self:
            self.move_to_end(key)
            return self[key]
        value = self[key] = factory()
        while len(self) > self.maxsize:
            self.popitem(last=False)
        return value


# =============================================================================
# ① Tool Ordering (KV Cache Stability)
# =============================================================================

def _tool_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name", ""))
    return str(getattr(tool, "name", "") or "")


def sort_tools_for_cache(tools: Optional[list]) -> list:
    """도구를 이름순으로 정렬합니다. 내장 도구 먼저, MCP 도구(mcp__*)는 뒤에 정렬합니다."""
    items = list(tools or [])
    builtin = sorted((t for t in items if not _tool_name(t).startswith("mcp__")), key=_tool_name)
    mcp = sorted((t for t in items if _tool_name(t).startswith("mcp__")), key=_tool_name)
    return builtin + mcp


# =============================================================================
# ③ User Context Builders (Session-Frozen HumanMessage)
# =============================================================================

def resolve_memory_snapshot(
    memory_snapshot: str = "",
    recalled_memory: str = "",
) -> str:
    """User Context(# memorySnapshot)에 세션 시작 시 1회 동결할 Semantic Memory 스냅샷을 반환합니다."""
    return (memory_snapshot or recalled_memory or "").strip()


def format_workspace_lines(ctx: Dict[str, Any]) -> List[str]:
    """세션 전용 작업 폴더 경로 안내 줄."""
    ws_root = ctx.get("workspace_dir")
    if not ws_root:
        return []
    return [
        f"- Session Workspace Root: {ws_root}",
        f"  - Plan Dir (plan_state/extraction_plan): {ctx.get('plan_dir') or f'{ws_root}/plan'}",
        f"  - Scripts Dir (.py scripts): {ctx.get('scripts_dir') or f'{ws_root}/scripts'}",
        f"  - Outputs Dir (data/charts/reports): {ctx.get('outputs_dir') or f'{ws_root}/outputs'}",
        f"  - Logs Dir (audit.jsonl): {ctx.get('logs_dir') or f'{ws_root}/logs'}",
    ]


def format_session_context(session_context: Optional[Dict[str, Any]]) -> str:
    """세션 컨텍스트 딕셔너리를 # sessionContext 마크다운 블록으로 포맷합니다."""
    if not session_context:
        return ""
    items: List[str] = []
    field_map = (
        ("current_date", "Current Date"),
        ("cwd", "Working Directory (CWD)"),
        ("os", "Host OS"),
        ("session_id", "Session ID"),
        ("user_id", "User ID"),
        ("user_permission", "User Permission"),
        ("active_project", "Active Project"),
        ("git_status", "Git Branch/Status"),
    )
    for key, label in field_map:
        val = session_context.get(key)
        if val is not None and str(val).strip():
            items.append(f"- {label}: {val}")
    items.extend(format_workspace_lines(session_context))
    return "\n".join(items)


def format_skill_entry(skill: Dict[str, str]) -> str:
    """스킬 메타데이터 1건을 카탈로그/델타용 한 줄 항목으로 포맷합니다."""
    desc = " ".join(str(skill.get("description", "")).split())
    if len(desc) > SKILL_DESCRIPTION_MAX_CHARS:
        desc = desc[: SKILL_DESCRIPTION_MAX_CHARS - 1] + "…"
    path_part = f" (`{skill['path']}`)" if skill.get("path") else ""
    return f"- **{skill['name']}**{path_part}: {desc}"


def format_skill_catalog(
    skills: Sequence[Dict[str, str]],
    skill_guidelines: str = "",
) -> str:
    """스킬 실행 지침과 스킬 목록을 # skillCatalog 본문으로 포맷합니다."""
    parts: List[str] = []
    guidelines_text = (skill_guidelines or "").strip()
    if guidelines_text and guidelines_text != "Content not available.":
        parts.append(f"## Skill Execution Policy\n{guidelines_text}")

    entries = [format_skill_entry(s) for s in (skills or []) if isinstance(s, dict) and s.get("name")]
    if entries:
        intro = (
            "The following skills are available. Before using a skill, read its documentation "
            "(path shown in parentheses) with `file_read`:"
        )
        parts.append(f"{intro}\n<skills>\n" + "\n".join(entries) + "\n</skills>")

    return "\n\n".join(parts)


def build_user_context(
    session_context: Optional[Dict[str, Any]] = None,
    skills: Optional[Sequence[Dict[str, str]]] = None,
    skill_guidelines: str = "",
    memory_snapshot: str = "",
    project_rules: str = "",
) -> Dict[str, str]:
    """사용자 컨텍스트 섹션 딕셔너리를 조립합니다."""
    context: Dict[str, str] = {}
    session_block = format_session_context(session_context)
    if session_block:
        context["sessionContext"] = session_block
    skill_block = format_skill_catalog(skills or (), skill_guidelines=skill_guidelines)
    if skill_block:
        context["skillCatalog"] = skill_block
    if memory_snapshot and memory_snapshot.strip():
        context["memorySnapshot"] = memory_snapshot.strip()
    if project_rules and project_rules.strip():
        context["projectRules"] = project_rules.strip()
    return context


def make_user_context_message(context: Dict[str, str]) -> HumanMessage:
    """사용자 컨텍스트를 담은 <system-reminder> 메시지 (출처 표식 포함)."""
    body = "\n\n".join(f"# {key}\n{value}" for key, value in context.items())
    return HumanMessage(
        content=f"<system-reminder>\n{USER_CONTEXT_INTRO}\n{body}\n\n{USER_CONTEXT_FOOTER}\n</system-reminder>\n",
        additional_kwargs=origin_kwargs(ORIGIN_USER_CONTEXT),
    )


def prepend_user_context(
    messages: List[BaseMessage],
    session_context: Optional[Dict[str, Any]] = None,
    skills: Optional[Sequence[Dict[str, str]]] = None,
    skill_guidelines: str = "",
    memory_snapshot: str = "",
    project_rules: str = "",
) -> List[BaseMessage]:
    """대화 맨 앞(SystemMessage 바로 뒤)에 사용자 컨텍스트 메시지를 끼워 넣습니다 (멱등)."""
    if not messages:
        return messages
    if any(message_origin(m) == ORIGIN_USER_CONTEXT for m in messages):
        return messages
    context = build_user_context(
        session_context=session_context,
        skills=skills,
        skill_guidelines=skill_guidelines,
        memory_snapshot=memory_snapshot,
        project_rules=project_rules,
    )
    if not context:
        return messages
    insert_at = 0
    while insert_at < len(messages) and isinstance(messages[insert_at], SystemMessage):
        insert_at += 1
    return messages[:insert_at] + [make_user_context_message(context)] + messages[insert_at:]


# =============================================================================
# ④ Append-Only Delta / Reminder Attachments
# =============================================================================

def _system_reminder(text: str) -> str:
    return f"<system-reminder>\n{text}\n</system-reminder>"


def _kwargs_of(msg: Any) -> Dict[str, Any]:
    return dict(getattr(msg, "additional_kwargs", None) or {})


def effective_skill_names(
    initial_skills: Sequence[Dict[str, str]],
    messages: Iterable[Any],
) -> Set[str]:
    """초기 스킬 카탈로그와 대화 속 skill_delta 알림을 순서대로 재생해 현재 활성 스킬 이름 집합을 구합니다."""
    names: Set[str] = {
        s["name"] for s in (initial_skills or ()) if isinstance(s, dict) and s.get("name")
    }
    for m in messages:
        if message_origin(m) == ORIGIN_SKILL_DELTA:
            kwargs = _kwargs_of(m)
            names.update(kwargs.get(SKILL_ADDED_KEY) or [])
            names.difference_update(kwargs.get(SKILL_REMOVED_KEY) or [])
    return names


def make_skill_delta_message(
    added: List[Dict[str, str]],
    removed: List[str],
) -> HumanMessage:
    """세션 중 스킬 추가/제거 변경분을 알리는 <system-reminder> 메시지."""
    sorted_added = sorted(added, key=lambda s: s["name"])
    sorted_removed = sorted(removed)
    sections: List[str] = ["# skillDelta"]
    if sorted_added:
        entries = "\n".join(format_skill_entry(s) for s in sorted_added)
        sections.append(
            "New skills became available (read the skill doc with `file_read` before using):\n"
            + entries
        )
    if sorted_removed:
        removed_lines = "\n".join(f"- {name}" for name in sorted_removed)
        sections.append(
            "The following skills were removed and are no longer available:\n"
            + removed_lines
        )
    return HumanMessage(
        content=_system_reminder("\n\n".join(sections)),
        additional_kwargs={
            **origin_kwargs(ORIGIN_SKILL_DELTA),
            SKILL_ADDED_KEY: [s["name"] for s in sorted_added],
            SKILL_REMOVED_KEY: sorted_removed,
        },
    )


def get_skill_delta(
    messages: List[Any],
    current_skills: Sequence[Dict[str, str]],
    initial_skills: Sequence[Dict[str, str]] = (),
) -> Optional[HumanMessage]:
    """초기 카탈로그+대화상 delta 기준 활성 스킬과 현재 스킬을 비교해 양방향 delta 메시지를 반환합니다."""
    known = effective_skill_names(initial_skills, messages)
    current_by_name: Dict[str, Dict[str, str]] = {
        s["name"]: s
        for s in (current_skills or ())
        if isinstance(s, dict) and s.get("name")
    }
    added = [current_by_name[name] for name in sorted(current_by_name) if name not in known]
    removed = sorted(name for name in known if name not in current_by_name)
    if not added and not removed:
        return None
    return make_skill_delta_message(added, removed)


def make_date_change_message(new_date: str) -> HumanMessage:
    """자정 경과 시 앞부분 캐시를 깨지 않고 대화 끝에 추가하는 날짜 변경 알림."""
    return HumanMessage(
        content=_system_reminder(
            f"The date has changed. Today's date is now {new_date}. "
            "DO NOT mention this to the user explicitly because they are already aware."
        ),
        additional_kwargs=origin_kwargs(ORIGIN_DATE_CHANGE),
    )


# =============================================================================
# PromptAssembler
# =============================================================================

class PromptAssembler:
    """정적 SystemMessage + 세션 동결 User Context + 대화 꼬리 Delta 알림 조립기."""

    def __init__(
        self,
        system_prompt: str = "",
        skill_guidelines: Optional[Union[str, Callable]] = None,
        skill_provider: Optional[Callable[[], List[Dict[str, str]]]] = None,
        project_rules: Optional[Union[str, Callable]] = None,
        *,
        system_rules: str = "",
    ):
        self.system_prompt = (system_prompt or system_rules or "").strip()
        self.skill_guidelines = skill_guidelines
        self.skill_provider = skill_provider
        self.project_rules = project_rules

        self._static_cache: Optional[str] = None
        self._skill_guidelines_cache: Optional[str] = None
        self._session_dates: _SessionLRU = _SessionLRU()

    @staticmethod
    def read_and_truncate_doc(
        source: Union[str, Callable],
        max_lines: int = 200,
        max_bytes: int = 25000,
    ) -> str:
        """경로, callable, 또는 문자열에서 문서를 읽고 줄/바이트 상한을 적용합니다."""
        if not source:
            return "Content not available."

        if callable(source):
            try:
                raw_content = str(source())
            except Exception as e:
                return f"Error evaluating document source: {e}"
        elif isinstance(source, str) and os.path.exists(source):
            try:
                with open(source, "r", encoding="utf-8") as f:
                    raw_content = f.read()
            except Exception as e:
                return f"Error reading file '{source}': {e}"
        elif isinstance(source, str):
            raw_content = source
        else:
            raw_content = str(source)

        lines = raw_content.splitlines(keepends=True)
        truncated = False

        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        content = "".join(lines)
        encoded_bytes = content.encode("utf-8")
        if len(encoded_bytes) > max_bytes:
            content = encoded_bytes[:max_bytes].decode("utf-8", errors="ignore")
            truncated = True

        if truncated:
            content += "\n\n... [Content truncated due to size limits] ..."

        return content.strip()

    def build_static_prompt(self) -> str:
        """② 정적 SystemMessage 본문을 조립·캐시합니다 (순수 prompt.py 역할 지침만 포함)."""
        if self._static_cache is None:
            self._static_cache = self.system_prompt
        return self._static_cache

    def clear_static_cache(self) -> None:
        """정적 프롬프트 및 스킬 실행 지침 캐시를 비웁니다."""
        self._static_cache = None
        self._skill_guidelines_cache = None

    def resolve_skill_guidelines(self) -> str:
        """skill_guidelines 소스(문자열·경로·callable)를 읽어 # skillCatalog용으로 캐시·반환합니다."""
        if self._skill_guidelines_cache is None:
            if not self.skill_guidelines:
                self._skill_guidelines_cache = ""
            else:
                text = self.read_and_truncate_doc(
                    self.skill_guidelines, max_lines=300, max_bytes=35000
                )
                self._skill_guidelines_cache = "" if text == "Content not available." else text
        return self._skill_guidelines_cache

    def current_skills(self) -> List[Dict[str, str]]:
        """skill_provider에서 현재 스킬 메타데이터 목록을 조회합니다."""
        if not self.skill_provider:
            return []
        try:
            return list(self.skill_provider() or [])
        except Exception:
            return []

    def resolve_project_rules(self) -> str:
        """project_rules 소스(문자열·경로·callable)를 평가합니다."""
        if not self.project_rules:
            return ""
        text = self.read_and_truncate_doc(self.project_rules, max_lines=500, max_bytes=50000)
        return "" if text == "Content not available." else text

    def session_date(self, session_id: str = "unknown") -> str:
        """세션 시작 날짜를 세션 내내 고정해 반환합니다."""
        return self._session_dates.get_or_create(session_id or "unknown", get_local_iso_date)

    def build_user_context_message(
        self,
        session_context: Optional[Dict[str, Any]] = None,
        skills: Optional[Sequence[Dict[str, str]]] = None,
        skill_guidelines: Optional[str] = None,
        memory_snapshot: str = "",
        project_rules: Optional[str] = None,
    ) -> Optional[HumanMessage]:
        """③ User Context <system-reminder> 메시지를 직접 생성합니다."""
        effective_skills = self.current_skills() if skills is None else list(skills)
        effective_guidelines = (
            self.resolve_skill_guidelines() if skill_guidelines is None else skill_guidelines
        )
        effective_rules = self.resolve_project_rules() if project_rules is None else project_rules
        context = build_user_context(
            session_context=session_context,
            skills=effective_skills,
            skill_guidelines=effective_guidelines,
            memory_snapshot=memory_snapshot,
            project_rules=effective_rules,
        )
        if not context:
            return None
        return make_user_context_message(context)

    def assemble(
        self,
        user_input: str,
        session_context: Optional[dict] = None,
        chat_history: Optional[list] = None,
        initial_skills: Optional[List[Dict[str, str]]] = None,
    ) -> List[BaseMessage]:
        """스탠드얼론 요청 메시지 리스트를 조립합니다 (테스트/노트북 시뮬레이션용)."""
        ctx = dict(session_context or {})
        sid = str(ctx.get("session_id") or "unknown")
        if "current_date" not in ctx:
            ctx["current_date"] = self.session_date(sid)

        static_text = self.build_static_prompt()
        assembled: List[BaseMessage] = [SystemMessage(content=static_text)] if static_text else []
        if chat_history:
            assembled.extend(chat_history)
        assembled.append(HumanMessage(content=user_input))

        skills_snapshot = self.current_skills() if initial_skills is None else list(initial_skills)
        memory_snapshot = resolve_memory_snapshot(
            memory_snapshot=str(ctx.get("memory_snapshot", "") or ""),
            recalled_memory=str(ctx.get("recalled_memory", "") or ""),
        )
        assembled = prepend_user_context(
            assembled,
            session_context=ctx,
            skills=skills_snapshot,
            skill_guidelines=self.resolve_skill_guidelines(),
            memory_snapshot=memory_snapshot,
            project_rules=self.resolve_project_rules(),
        )

        if self.skill_provider is not None:
            delta = get_skill_delta(assembled, self.current_skills(), initial_skills=skills_snapshot)
            if delta is not None:
                assembled.append(delta)

        return assembled


# =============================================================================
# Production AgentMiddleware
# =============================================================================

class PromptState(AgentState):
    """PromptAssemblerMiddleware가 checkpointer state에 유지하는 세션 상태."""
    session_start_date: NotRequired[str]
    last_emitted_date: NotRequired[str]
    initial_skills: NotRequired[List[Dict[str, str]]]


class PromptAssemblerMiddleware(AgentMiddleware):
    """정적 SystemMessage, 세션 동결 User Context, 꼬리 Delta/알림을 조립하는 AgentMiddleware."""

    state_schema = PromptState

    def __init__(
        self,
        assembler: PromptAssembler,
        enable_cache_control: bool = True,
    ):
        self.assembler = assembler
        self.enable_cache_control = enable_cache_control
        self._session_env: _SessionLRU = _SessionLRU()
        self._session_initial_skills: _SessionLRU = _SessionLRU()

    @staticmethod
    def _resolve_ids(runtime: Any) -> Dict[str, Any]:
        """runtime.context → config.configurable → execution_info 순서로 세션·사용자 id를 찾습니다."""
        ctx = getattr(runtime, "context", None) if runtime is not None else None
        user_id = getattr(ctx, "user_id", "default") if ctx else "default"
        session_id = getattr(ctx, "session_id", "unknown") if ctx else "unknown"
        parent_session_id = getattr(ctx, "parent_session_id", "") if ctx else ""

        config = getattr(runtime, "config", None) if runtime is not None else None
        if config and isinstance(config, dict):
            configurable = config.get("configurable", {}) or {}
            tid = configurable.get("thread_id")
            if tid:
                session_id = str(tid)
            cfg_uid = configurable.get("user_id")
            if cfg_uid and (not user_id or user_id == "default"):
                user_id = str(cfg_uid)
            cfg_ptid = configurable.get("parent_thread_id")
            if cfg_ptid and not parent_session_id:
                parent_session_id = str(cfg_ptid)

        exec_info = getattr(runtime, "execution_info", None) if runtime is not None else None
        if exec_info and getattr(exec_info, "thread_id", None):
            session_id = str(exec_info.thread_id)

        return {
            "ctx": ctx,
            "session_id": session_id or "unknown",
            "user_id": user_id,
            "parent_session_id": parent_session_id,
        }

    def before_model(self, state: Dict[str, Any], runtime: Any = None) -> Optional[Dict[str, Any]]:
        update: Dict[str, Any] = {}
        new_messages: List[BaseMessage] = []
        messages = list(state.get("messages") or [])

        # 1) 세션 시작 날짜 고정 & 자정 경과 date_change 알림
        today = get_local_iso_date()
        start = state.get("session_start_date")
        if not start:
            update.update({"session_start_date": today, "last_emitted_date": today})
        elif state.get("last_emitted_date", start) != today:
            new_messages.append(make_date_change_message(today))
            update["last_emitted_date"] = today

        # 2) 초기 스킬 스냅샷 고정 및 세션 중 스킬 변화(양방향 Delta) 알림
        if self.assembler.skill_provider is not None:
            current_skills = self.assembler.current_skills()
            state_initial = state.get("initial_skills")
            if state_initial is None:
                update["initial_skills"] = current_skills
            else:
                delta = get_skill_delta(messages, current_skills, initial_skills=state_initial)
                if delta is not None:
                    new_messages.append(delta)

        if new_messages:
            update["messages"] = new_messages
        return update or None

    async def abefore_model(self, state: Dict[str, Any], runtime: Any = None) -> Optional[Dict[str, Any]]:
        return self.before_model(state, runtime)

    def _session_environment(self, ids: Dict[str, Any]) -> Dict[str, str]:
        """세션당 1회: 세션 전용 작업 폴더 경로 캐시."""
        key = f"{ids['user_id']}|{ids['session_id']}|{ids['parent_session_id']}"

        def compute() -> Dict[str, str]:
            try:
                from app.utils.workspace import resolve_session_workspace

                ws = resolve_session_workspace(
                    user_id=ids["user_id"],
                    session_id=ids["session_id"],
                    parent_session_id=ids["parent_session_id"] or None,
                    ensure_exists=False,
                )
                return {
                    "workspace_dir": ws.rel_root,
                    "plan_dir": ws.rel_plan_dir,
                    "scripts_dir": ws.rel_scripts_dir,
                    "outputs_dir": ws.rel_outputs_dir,
                    "logs_dir": ws.rel_logs_dir,
                }
            except Exception:
                return {}

        return self._session_env.get_or_create(key, compute)

    def _prepare_messages(self, request) -> list:
        ids = self._resolve_ids(request.runtime)
        ctx, session_id = ids["ctx"], ids["session_id"]
        state = getattr(request, "state", None) or {}

        session_date = state.get("session_start_date") or self.assembler.session_date(session_id)
        cwd = getattr(ctx, "cwd", os.getcwd()) if ctx else os.getcwd()
        session_context: Dict[str, Any] = {
            "current_date": session_date,
            "cwd": cwd,
            "os": os.name,
            "session_id": session_id,
            "user_id": ids["user_id"],
        }

        ctx_ws_dir = (getattr(ctx, "workspace_dir", "") or "").strip() if ctx else ""
        if ctx_ws_dir:
            ws_root_rel = ctx_ws_dir.rstrip("/")
            session_context.update({
                "workspace_dir": ws_root_rel,
                "plan_dir": f"{ws_root_rel}/plan",
                "scripts_dir": f"{ws_root_rel}/scripts",
                "outputs_dir": f"{ws_root_rel}/outputs",
                "logs_dir": f"{ws_root_rel}/logs",
            })
        else:
            env = self._session_environment(ids)
            session_context.update(env)
            if env.get("workspace_dir") and ctx is not None and hasattr(ctx, "workspace_dir"):
                ctx.workspace_dir = env["workspace_dir"]

        # ② Static SystemMessage
        static_text = self.assembler.build_static_prompt()
        if static_text:
            static_kwargs = {"cache_control": {"type": "ephemeral"}} if self.enable_cache_control else {}
            system_messages: List[BaseMessage] = [
                SystemMessage(content=static_text, additional_kwargs=static_kwargs)
            ]
        else:
            system_messages = []

        # 기존 SystemMessage(단, Compaction 관련 SystemMessage는 보존) 및 빈 메시지 필터링
        filtered_msgs: List[BaseMessage] = []
        for m in request.messages:
            if isinstance(m, SystemMessage):
                if not is_compaction_artifact(m):
                    continue
            content = getattr(m, "content", "")
            tool_calls = getattr(m, "tool_calls", None)
            if not content and not tool_calls:
                continue
            filtered_msgs.append(m)

        # ③ User Context Message (세션 동결: sessionContext + initial skillCatalog + memorySnapshot + projectRules)
        state_initial = state.get("initial_skills")
        if state_initial is not None:
            initial_skills = list(state_initial)
        elif self.assembler.skill_provider is not None:
            initial_skills = list(
                self._session_initial_skills.get_or_create(session_id, self.assembler.current_skills)
            )
        else:
            initial_skills = []

        memory_snapshot = resolve_memory_snapshot(
            memory_snapshot=getattr(ctx, "memory_snapshot", "") if ctx else "",
            recalled_memory=getattr(ctx, "recalled_memory", "") if ctx else "",
        )

        result_messages = system_messages + filtered_msgs
        return prepend_user_context(
            result_messages,
            session_context=session_context,
            skills=initial_skills,
            skill_guidelines=self.assembler.resolve_skill_guidelines(),
            memory_snapshot=memory_snapshot,
            project_rules=self.assembler.resolve_project_rules(),
        )

    def _override(self, request):
        overrides: Dict[str, Any] = {"messages": self._prepare_messages(request)}
        tools = list(getattr(request, "tools", None) or [])
        if tools:
            overrides["tools"] = sort_tools_for_cache(tools)
        return request.override(**overrides)

    def wrap_model_call(self, request, handler):
        return handler(self._override(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._override(request))


def create_prompt_assembler_middleware(
    assembler: PromptAssembler,
    enable_cache_control: bool = True,
) -> PromptAssemblerMiddleware:
    """Simplified PromptAssemblerMiddleware 인스턴스를 생성합니다."""
    return PromptAssemblerMiddleware(assembler, enable_cache_control=enable_cache_control)
