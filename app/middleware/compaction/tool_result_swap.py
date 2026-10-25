"""
===============================================================================
[H-01a] Tool Result Swap Middleware
===============================================================================
큰 도구 결과를 디스크에 저장하고, 모델에게는 미리보기와 파일 경로만 보여줍니다.

- 도구가 끝나는 즉시(wrap_tool_call) 한 번만 저장합니다. state에는 처음부터 미리보기가 들어가므로
  매 모델 호출마다 다시 처리하지 않습니다.
- 파일 이름은 tool_call_id라서 같은 결과를 두 번 쓰지 않습니다.
- 저장 위치: swap_dir를 주지 않으면 유저·세션 워크스페이스
  (artifacts/users/{user_id}/sessions/{session_id}/tool-results/, 서브에이전트는 그 아래 subagents/...)에,
  swap_dir를 주면 {swap_dir}/{thread_id}/에 저장합니다.
- file_read 결과는 저장하지 않습니다. 저장한 파일을 file_read로 다시 읽으면 그 결과가 또 저장되어
  모델이 끝내 내용을 볼 수 없는 순환이 생기기 때문입니다 (file_read는 limit으로 스스로 분량을 제한).
- 텍스트가 아닌 결과(이미지 블록 등)와 Command를 돌려주는 도구는 건드리지 않습니다.

같은 아이디어를 쓰는 곳: Claude Code의 tool result persistence(<persisted-output>),
Deep Agents의 큰 도구 결과 파일 저장.
===============================================================================
"""

import os
import re
import uuid
from typing import Iterable, Optional, Tuple

from langchain_core.messages import ToolMessage
from langchain.agents.middleware import AgentMiddleware


DEFAULT_MAX_RESULT_CHARS = 10_000
DEFAULT_PREVIEW_CHARS = 2_000
DEFAULT_EXCLUDE_TOOLS = ("file_read",)
PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"


def resolve_session_key() -> str:
    """현재 LangGraph 런의 thread_id. 그래프 밖에서 호출하거나 thread_id가 없으면 'default'."""
    try:
        from langgraph.config import get_config
        config = get_config()
    except Exception:
        return "default"
    thread_id = ((config or {}).get("configurable") or {}).get("thread_id")
    return str(thread_id) if thread_id else "default"


def _workspace_tool_results_dir(runtime) -> str:
    """도구 실행 runtime의 (user_id, thread_id, parent_session_id)로 세션 워크스페이스의 tool-results 경로를 만듭니다."""
    from app.utils.workspace import resolve_session_workspace

    ctx = getattr(runtime, "context", None)
    user_id = getattr(ctx, "user_id", None) or "default"
    parent_session_id = getattr(ctx, "parent_session_id", None) or None
    ws = resolve_session_workspace(user_id=user_id, session_id=resolve_session_key(),
                                   parent_session_id=parent_session_id)
    return str(ws.root_dir / "tool-results")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def _format_size(chars: int) -> str:
    return f"{chars / 1024:.1f}KB" if chars >= 1024 else f"{chars} chars"


class ToolResultSwapMiddleware(AgentMiddleware):
    """max_result_chars를 넘는 도구 결과를 디스크로 옮기고 미리보기로 바꿉니다."""

    def __init__(self, swap_dir: Optional[str] = None,
                 max_result_chars: int = DEFAULT_MAX_RESULT_CHARS,
                 preview_chars: int = DEFAULT_PREVIEW_CHARS,
                 exclude_tools: Iterable[str] = DEFAULT_EXCLUDE_TOOLS):
        self.swap_dir = swap_dir
        self.max_result_chars = max_result_chars
        self.preview_chars = preview_chars
        self.exclude_tools = set(exclude_tools)

    def generate_preview(self, content: str) -> Tuple[str, bool]:
        """한도 안에서 마지막 줄바꿈 위치로 자릅니다 (줄바꿈이 너무 앞이면 한도 그대로)."""
        if len(content) <= self.preview_chars:
            return content, False
        truncated = content[:self.preview_chars]
        last_newline = truncated.rfind("\n")
        cut = last_newline if last_newline > self.preview_chars * 0.5 else self.preview_chars
        return content[:cut], True

    def target_dir(self, runtime=None) -> str:
        if self.swap_dir:
            return os.path.abspath(os.path.join(self.swap_dir, _safe_name(resolve_session_key())))
        return os.path.abspath(_workspace_tool_results_dir(runtime))

    def persist(self, content: str, tool_call_id: str, runtime=None) -> Optional[str]:
        """결과를 파일로 저장하고 모델에게 보낼 대체 문자열을 반환합니다. 저장에 실패하면 None."""
        directory = self.target_dir(runtime)
        path = os.path.join(directory, f"{_safe_name(tool_call_id or uuid.uuid4().hex)}.txt")
        try:
            os.makedirs(directory, exist_ok=True)
            with open(path, "x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            pass
        except OSError:
            return None
        preview, has_more = self.generate_preview(content)
        return (
            f"{PERSISTED_OUTPUT_TAG}\n"
            f"Output too large ({_format_size(len(content))}). Full output saved to: {path}\n"
            f"Use file_read(file_path=..., offset=..., limit=...) or grep_search on this file "
            f"to inspect specific parts instead of re-running the tool.\n\n"
            f"Preview (first {_format_size(len(preview))}):\n"
            f"{preview}{chr(10) + '...' if has_more else ''}\n"
            f"{PERSISTED_OUTPUT_CLOSING_TAG}"
        )

    @staticmethod
    def is_persisted(msg: ToolMessage) -> bool:
        return isinstance(msg.content, str) and msg.content.startswith(PERSISTED_OUTPUT_TAG)

    def swap_if_large(self, msg: ToolMessage, tool_name: Optional[str] = None, runtime=None) -> ToolMessage:
        name = tool_name or getattr(msg, "name", None)
        if (not isinstance(msg.content, str) or name in self.exclude_tools
                or len(msg.content) <= self.max_result_chars or self.is_persisted(msg)):
            return msg
        replacement = self.persist(msg.content, msg.tool_call_id, runtime)
        if replacement is None:
            return msg
        return msg.model_copy(update={"content": replacement})

    def _apply(self, request, result):
        if not isinstance(result, ToolMessage):
            return result
        tool_name = (getattr(request, "tool_call", None) or {}).get("name")
        return self.swap_if_large(result, tool_name, getattr(request, "runtime", None))

    def wrap_tool_call(self, request, handler):
        return self._apply(request, handler(request))

    async def awrap_tool_call(self, request, handler):
        return self._apply(request, await handler(request))
