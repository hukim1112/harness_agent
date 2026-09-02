"""
===============================================================================
[H-05] 5-Layer Prompt Assembler with Cache Control & Async/Sync Middleware
===============================================================================
Source: Claude Code Architecture Spec & Frontier Agent Lab

Claude Code 표준 5계층 프롬프트 조립기 (Prompt Caching & Memory Architecture):

[STATIC PREFIX: GPU KV-Cache HIT 🎯]
- Layer 1: System Identity & Core Role (PROMPT.md / System Rules)
- Layer 2: Tool Capabilities (알파벳 순 정렬) + Skills Catalog
- ⚡ __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__ (Cache Control 마킹 지점)

[DYNAMIC SUFFIX: 매 턴/세션 가변 영역 ⚡]
- Layer 3: Dynamic Session Context (CWD, OS, Session ID, User Permission, Git Branch)
- Layer 4: Memory & Dynamic Documents (recalled_memory, MEMORY.md, USER.md, MCP.md 등)
- Layer 5: User & Local Project Rules (CLAUDE.md, AGENT.md, CONVENTIONS.md)

통합 미들웨어: PromptAssemblerMiddleware (AgentMiddleware 상속 - 동기/비동기 100% 지원)
- merge_system=False: SystemMessage 2개 (Static cache_control: ephemeral + Dynamic)
- merge_system=True : SystemMessage 1개 (단일 System Prompt로 결합 출력)
===============================================================================
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Callable
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents.middleware import AgentMiddleware


class PromptAssembler:
    """Claude Code style 5-layer prompt assembler for Prompt Caching & Memory optimization.

    Layers:
    - Layer 1: System Identity & Core Role (Static Rules)
    - Layer 2: Tool Capabilities (Alphabetically sorted) + Skills Catalog
    - Boundary Marker: __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__
    - Layer 3: Dynamic Session Context (CWD, OS, Session ID, Permissions, Git Branch)
    - Layer 4: Memory & Dynamic Documents (Recalled Memory, MEMORY.md, USER.md, MCP.md)
    - Layer 5: User & Local Project Rules (CLAUDE.md, AGENT.md, CONVENTIONS.md)
    """

    def __init__(
        self,
        system_rules: str,
        tool_schemas: Optional[list] = None,
        skill_catalog: Optional[Union[str, Callable]] = None,
        memory_path: Optional[str] = None,
        user_path: Optional[str] = None,
        agent_rules_path: Optional[str] = None,
        l4_docs: Optional[Dict[str, Union[str, Callable]]] = None,
        l5_docs: Optional[Dict[str, Union[str, Callable]]] = None,
    ):
        self.system_rules = system_rules
        self.tool_schemas = tool_schemas or []
        self.skill_catalog = skill_catalog
        self.boundary_marker = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"

        # Multi-document registries for Layer 4 & Layer 5
        self.l4_docs: Dict[str, Union[str, Callable]] = dict(l4_docs or {})
        self.l5_docs: Dict[str, Union[str, Callable]] = dict(l5_docs or {})

        # Backward compatibility / convenient path binding for Semantic Memory
        if memory_path:
            self.l4_docs["MEMORY.md"] = memory_path
        if user_path:
            self.l4_docs["USER.md"] = user_path

        # Project Context Rules (Layer 5)
        if agent_rules_path:
            self.l5_docs["AGENT.md"] = agent_rules_path

    def set_skill_catalog(self, source: Union[str, Callable]) -> None:
        """Layer 2에 스킬 카탈로그/가이드라인을 설정합니다."""
        self.skill_catalog = source

    def add_l4_doc(self, name: str, source: Union[str, Callable]) -> None:
        """Layer 4에 동적 세션/메모리 문서를 추가합니다 (e.g. 'MEMORY.md', 'USER.md', 'MCP.md')."""
        self.l4_docs[name] = source

    def remove_l4_doc(self, name: str) -> None:
        """Layer 4에서 특정 문서를 제거합니다."""
        self.l4_docs.pop(name, None)

    def add_l5_doc(self, name: str, source: Union[str, Callable]) -> None:
        """Layer 5에 프로젝트 컨텍스트 규칙 문서를 추가합니다 (e.g. 'CLAUDE.md', 'AGENT.md')."""
        self.l5_docs[name] = source

    def remove_l5_doc(self, name: str) -> None:
        """Layer 5에서 특정 문서를 제거합니다."""
        self.l5_docs.pop(name, None)

    # ── Formatting Helpers ──

    def format_tool_capabilities(self) -> str:
        """Formats L2 tool capabilities sorted alphabetically by name for KV cache consistency."""
        if not self.tool_schemas:
            return "No registered tools."

        def get_tool_name(schema: Any) -> str:
            if isinstance(schema, dict):
                return schema.get("name", "")
            return getattr(schema, "name", str(schema))

        sorted_tools = sorted(self.tool_schemas, key=get_tool_name)

        tool_lines = []
        for idx, tool in enumerate(sorted_tools):
            name = get_tool_name(tool)
            desc = ""
            args_dict = {}

            if isinstance(tool, dict):
                desc = tool.get("description", "").strip()
                raw_args = tool.get("args") or tool.get("parameters") or {}
                if isinstance(raw_args, dict):
                    args_dict = raw_args.get("properties", raw_args)
            else:
                desc = getattr(tool, "description", "").strip()
                if hasattr(tool, "args") and isinstance(tool.args, dict):
                    args_dict = tool.args
                elif hasattr(tool, "args_schema") and tool.args_schema:
                    try:
                        schema = tool.args_schema.schema()
                        args_dict = schema.get("properties", {})
                    except Exception:
                        args_dict = {}

            # 도구 헤더 및 설명
            tool_str = f"### [{idx + 1}] `{name}`\n{desc}"

            # 매개변수 스키마를 읽기 쉬운 마크다운 목록으로 렌더링
            if args_dict and isinstance(args_dict, dict):
                param_lines = []
                for param_name, param_info in args_dict.items():
                    if isinstance(param_info, dict):
                        p_type = param_info.get("type", "any")
                        p_desc = param_info.get("description", "")
                        p_default = param_info.get("default", None)
                        default_str = f", default: {p_default}" if p_default is not None else ""
                        desc_str = f" — {p_desc}" if p_desc else ""
                        param_lines.append(f"  - `{param_name}` (*{p_type}*{default_str}){desc_str}")
                    else:
                        param_lines.append(f"  - `{param_name}`: {param_info}")
                if param_lines:
                    tool_str += "\n\n**Parameters:**\n" + "\n".join(param_lines)

            tool_lines.append(tool_str)

        return "\n\n".join(tool_lines)

    @staticmethod
    def read_and_truncate_doc(
        source: Union[str, Callable],
        max_lines: int = 200,
        max_bytes: int = 25000,
    ) -> str:
        """Reads content from path, callable, or text string with line & byte truncation."""
        if not source:
            return "Content not available."

        # Evaluate callable source
        if callable(source):
            try:
                raw_content = str(source())
            except Exception as e:
                return f"Error evaluating document source: {e}"
        # Check if source is a file path
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

    # ── Layer Builders ──

    def build_static_content(self) -> str:
        """Assembles Layers 1~2 + Boundary Marker (Static KV Cache Target)."""
        tool_str = self.format_tool_capabilities()
        skill_str = ""
        if self.skill_catalog:
            raw_skill = self.read_and_truncate_doc(
                self.skill_catalog, max_lines=300, max_bytes=35000
            )
            skill_str = f"\n\n---\n## 📦 Layer 2.2: Available Skills Catalog & Execution Policy\n{raw_skill}"

        return (
            f"=== Layer 1: System Identity & Core Role ===\n{self.system_rules}\n\n"
            f"=== Layer 2: Capabilities (Tools & Skills) ===\n\n"
            f"## 🛠️ Layer 2.1: Registered Tool Capabilities (Alphabetical)\n{tool_str}"
            f"{skill_str}\n\n"
            f"{self.boundary_marker}"
        )

    def build_dynamic_content(self, session_context: dict) -> str:
        """Assembles Layers 3~5 (Dynamic Session, Memory, and Project Context)."""
        # --- Layer 3: Dynamic Session Context ---
        current_date_str = session_context.get("current_date") or datetime.now().strftime("%Y-%m-%d")
        session_items = [
            f"- Current Date: {current_date_str}",
            f"- Working Directory (CWD): {session_context.get('cwd', '/workspace')}",
            f"- Session ID: {session_context.get('session_id', 'unknown')}",
            f"- Host OS: {session_context.get('os', os.name)}",
        ]
        if "user_permission" in session_context:
            session_items.append(f"- User Permission: {session_context['user_permission']}")
        if "active_project" in session_context:
            session_items.append(f"- Active Project: {session_context['active_project']}")
        if "git_status" in session_context:
            session_items.append(f"- Git Branch/Status: {session_context['git_status']}")

        l3_sections = [
            "=== Layer 3: Dynamic Session Context ===",
            "Session Information:\n" + "\n".join(session_items),
        ]

        # --- Layer 4: Memory & Dynamic Documents ---
        # ────────────────────────────────────────────────────────────────────
        # L4의 메모리 데이터는 MemoryMiddleware.before_agent()가 ctx.recalled_memory에
        # 주입한 내용을 session_context["recalled_memory"]로 읽어 출력합니다.
        #
        # 주입 내용 (MemoryMiddleware 경유):
        #   1. Semantic Memory Frozen Snapshot (MEMORY.md + USER.md)
        #      → 세션 전환 시 1회 load_from_disk() → format_for_prompt()
        #   2. Episodic Memory FTS5 힌트 (과거 세션 요약 top-k)
        #      → 매 턴 유저 쿼리 기반 search_sessions()
        #
        # l4_docs에는 비메모리 동적 문서(MCP.md 등)만 등록합니다.
        # USER.md/MEMORY.md는 여기 등록하지 않습니다 (이중 주입 방지).
        # ────────────────────────────────────────────────────────────────────
        l4_sections = [
            "=== Layer 4: Memory & Dynamic Documents ==="
        ]

        # 1. Recalled Memory (MemoryMiddleware 경유: Semantic Frozen Snapshot + Episodic FTS5 힌트)
        recalled = session_context.get("recalled_memory", "")
        if recalled and recalled.strip():
            l4_sections.append(f"[Recalled Memory (injected by MemoryMiddleware)]:\n{recalled.strip()}")

        # 2. 비메모리 동적 문서 (MCP.md 등 — USER.md/MEMORY.md는 여기 등록하지 않음)
        if self.l4_docs:
            for doc_name, source in self.l4_docs.items():
                doc_content = self.read_and_truncate_doc(source, max_lines=300, max_bytes=35000)
                l4_sections.append(f"[{doc_name}]:\n{doc_content}")
        elif not recalled or not recalled.strip():
            l4_sections.append("No dynamic memory or session documents active.")

        # --- Layer 5: User & Local Project Rules ---
        l5_sections = [
            "=== Layer 5: User & Local Project Rules ==="
        ]

        if not self.l5_docs:
            l5_sections.append("No local project rules (AGENT.md/CLAUDE.md) provided.")
        else:
            for doc_name, source in self.l5_docs.items():
                doc_content = self.read_and_truncate_doc(source, max_lines=500, max_bytes=50000)
                l5_sections.append(f"[{doc_name} Rules]:\n{doc_content}")

        full_l3 = "\n\n".join(l3_sections)
        full_l4 = "\n\n".join(l4_sections)
        full_l5 = "\n\n".join(l5_sections)

        return f"{full_l3}\n\n{full_l4}\n\n{full_l5}"

    def build_system_prompt(self, session_context: dict) -> str:
        """Assembles all 5 layers into a single prompt string."""
        static_part = self.build_static_content()
        dynamic_part = self.build_dynamic_content(session_context)
        return f"{static_part}\n\n{dynamic_part}"

    def assemble(self, user_input: str, session_context: dict, chat_history: list = None) -> list:
        """Assembles full list of messages as structured SystemMessages + Chat History + HumanMessage."""
        static_content = self.build_static_content()
        dynamic_content = self.build_dynamic_content(session_context)

        assembled = [
            SystemMessage(content=static_content),
            SystemMessage(content=dynamic_content),
        ]

        if chat_history:
            assembled.extend(chat_history)

        assembled.append(HumanMessage(content=user_input))
        return assembled


# =============================================================================
# Production AgentMiddleware Class (Supports both Sync & Async Agent calls)
# =============================================================================

class PromptAssemblerMiddleware(AgentMiddleware):
    """Production AgentMiddleware implementing both wrap_model_call & awrap_model_call."""

    def __init__(self, assembler: PromptAssembler, merge_system: bool = False):
        self.assembler = assembler
        self.merge_system = merge_system

    def _prepare_messages(self, request) -> list:
        ctx = getattr(request.runtime, "context", None)
        session_context = {
            "cwd": getattr(ctx, "cwd", os.getcwd()) if ctx else os.getcwd(),
            "session_id": getattr(ctx, "session_id", "unknown") if ctx else "unknown",
            "os": os.name,
            "user_permission": getattr(ctx, "user_permission", "GUEST") if ctx else "GUEST",
            "active_project": getattr(ctx, "active_project", "UNKNOWN") if ctx else "UNKNOWN",
            "recalled_memory": getattr(ctx, "recalled_memory", "") if ctx else "",
        }

        # Retrieve thread_id from config if available
        config = getattr(request.runtime, "config", None)
        if config and isinstance(config, dict):
            tid = config.get("configurable", {}).get("thread_id")
            if tid:
                session_context["session_id"] = str(tid)

        if self.merge_system:
            # Single SystemMessage (L1~L5 All-in-one)
            full_system_text = self.assembler.build_system_prompt(session_context)
            system_messages = [SystemMessage(content=full_system_text)]
        else:
            # Dual SystemMessage (Static with cache_control + Dynamic)
            static_msg = SystemMessage(
                content=self.assembler.build_static_content(),
                additional_kwargs={"cache_control": {"type": "ephemeral"}},
            )
            dynamic_msg = SystemMessage(
                content=self.assembler.build_dynamic_content(session_context)
            )
            system_messages = [static_msg, dynamic_msg]

        # Filter out existing SystemMessages to avoid duplication, and clean empty messages
        filtered_msgs = []
        for m in request.messages:
            if isinstance(m, SystemMessage):
                continue
            # Prevent empty parts / Gemini 400 error
            content = getattr(m, "content", "")
            tool_calls = getattr(m, "tool_calls", None)
            if not content and not tool_calls:
                continue
            filtered_msgs.append(m)

        return system_messages + filtered_msgs

    def wrap_model_call(self, request, handler):
        new_messages = self._prepare_messages(request)
        new_request = request.override(messages=new_messages)
        return handler(new_request)

    async def awrap_model_call(self, request, handler):
        new_messages = self._prepare_messages(request)
        new_request = request.override(messages=new_messages)
        return await handler(new_request)


def create_prompt_assembler_middleware(assembler: PromptAssembler, merge_system: bool = False) -> PromptAssemblerMiddleware:
    """Creates a production PromptAssemblerMiddleware instance."""
    return PromptAssemblerMiddleware(assembler, merge_system=merge_system)
