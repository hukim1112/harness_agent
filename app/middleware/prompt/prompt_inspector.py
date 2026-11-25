"""Notebook/CLI prompt inspection helpers for the simplified PromptAssembler."""

import re
import unicodedata
from types import SimpleNamespace
from typing import Any, Iterable, Optional, Sequence

from langchain.agents.middleware import ModelRequest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.utils.message_markers import is_compaction_artifact, message_origin

from .prompt_assembler import SKILL_ADDED_KEY, SKILL_REMOVED_KEY


def _disp_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _disp_width(s))


def _msg_text(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    return " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content or [])


def _summarize_message(msg: Any, text: str) -> str:
    origin = message_origin(msg)
    if isinstance(msg, SystemMessage):
        if is_compaction_artifact(msg):
            return "Compaction system artifact"
        first_line = text.splitlines()[0].strip() if text.splitlines() else ""
        return first_line[:52] + ("…" if len(first_line) > 52 else "")

    if origin == "user_context":
        heads = re.findall(r"^#\s+([A-Za-z0-9_]+)", text, re.MULTILINE)
        return " · ".join(f"#{h}" for h in heads) if heads else "<system-reminder>"

    if origin == "skill_delta":
        ak = getattr(msg, "additional_kwargs", None) or {}
        added = list(ak.get(SKILL_ADDED_KEY) or [])
        removed = list(ak.get(SKILL_REMOVED_KEY) or [])
        segs = []
        if added:
            segs.append(f"+{len(added)}개 {added}")
        if removed:
            segs.append(f"-{len(removed)}개 {removed}")
        return "skillDelta (" + ", ".join(segs) + ")" if segs else "skillDelta"

    if origin == "date_change":
        m = re.search(r"Today's date is now \d{4}-\d{2}-\d{2}\.", text)
        if m:
            return f"The date has changed. {m.group(0)}"

    if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
        calls = ", ".join(f"{tc['name']}({tc.get('args', {})})" for tc in msg.tool_calls)
        return f"🔧 {calls[:54]}"

    flat = " ⏎ ".join(ln.strip() for ln in text.splitlines() if ln.strip())
    return flat[:52] + ("…" if len(flat) > 52 else "")


def _format_body_preview(msg: Any, max_skill_lines: int = 5) -> str:
    text = _msg_text(msg)
    if message_origin(msg) not in ("skill_delta", "user_context"):
        return text
    lines = text.splitlines()
    bullet_idx = [i for i, ln in enumerate(lines) if ln.startswith("- **")]
    if len(bullet_idx) <= max_skill_lines:
        return text
    if message_origin(msg) == "skill_delta":
        head = lines[: bullet_idx[max_skill_lines - 1] + 1]
        hidden = len(bullet_idx) - max_skill_lines
        return "\n".join(head + [f"... (외 {hidden}개 스킬 생략)", "</system-reminder>"])
    return text


def show_prompt_map(
    messages: Sequence[Any],
    title: str,
    tools: Optional[Sequence[Any]] = None,
    prev_messages: Optional[Sequence[Any]] = None,
    highlight_indices: Iterable[int] = (),
    show_bodies: Iterable[int] = (),
    max_skill_lines: int = 5,
) -> None:
    """조립된 요청의 tools 순서와 메시지 구조를 한눈에 출력합니다."""
    print("=" * 84)
    print(f"📌 {title}")
    print("=" * 84)
    if tools is not None:
        names = [t.get("name", "") if isinstance(t, dict) else getattr(t, "name", "") for t in tools]
        builtin = [n for n in names if not n.startswith("mcp__")]
        mcp = [n for n in names if n.startswith("mcp__")]
        print(f"🧰 ① tools 칸 (총 {len(names)}개): 내장 {builtin} → MCP {mcp}")

    highlight_set = {idx if idx >= 0 else len(messages) + idx for idx in highlight_indices}
    use_badge_col = (prev_messages is not None) or bool(highlight_set)

    prefix_alive = True
    cached_count = 0
    cached_chars = 0
    for i, m in enumerate(messages):
        text = _msg_text(m)
        origin = message_origin(m)
        if isinstance(m, SystemMessage):
            if is_compaction_artifact(m):
                role_tag = "System [Compaction]"
            else:
                cached = " +cache" if (getattr(m, "additional_kwargs", None) or {}).get("cache_control") else ""
                role_tag = f"System [정적 🔒{cached}]"
        elif isinstance(m, ToolMessage):
            role_tag = f"Tool({m.name})"
        elif isinstance(m, AIMessage):
            role_tag = "AI"
        else:
            role_tag = f"Human<{origin}>" if origin else "Human"

        is_cached = False
        if prev_messages is not None:
            if prefix_alive and i < len(prev_messages) and text == _msg_text(prev_messages[i]):
                is_cached = True
                cached_count += 1
                cached_chars += len(text)
            else:
                prefix_alive = False

        summary = _summarize_message(m, text)
        badge = ""
        if use_badge_col:
            if is_cached:
                badge_label = "[캐시 ✅]"
            elif i in highlight_set:
                if origin == "skill_delta":
                    badge_label = "[✨스킬]"
                else:
                    badge_label = "[✨추가]"
                summary = f"◀ {summary}"
            elif prev_messages is not None:
                badge_label = "[변경 ❌]" if i < len(prev_messages) else "[신규 🆕]"
            else:
                badge_label = ""
            badge = _pad(badge_label, 10) + " "

        print(f"  [{i:02d}] {badge}{_pad(role_tag, 32)} {len(text):>6,}자 | {summary}")

    if prev_messages is not None:
        if cached_count > 0:
            tail = (
                f" · 뒤 {len(messages) - cached_count}개 신규 (이 중 알림 {len(highlight_set)}개 ✨)"
                if highlight_set
                else f" · 뒤 {len(messages) - cached_count}개 신규 추가"
            )
            print(
                f"➡️  앞 [00]~[{cached_count - 1:02d}] 프리픽스 {cached_count}개 메시지 "
                f"100% 바이트 일치 ({cached_chars:,}자 캐시 재사용){tail}"
            )
        else:
            print(f"➡️  프리픽스 일치 메시지 없음 (총 {len(messages)}개 중 {len(messages)}개 신규 계산)")

    if show_bodies:
        print("\n--- 상세 내용 확인 ---")
        for raw_idx in show_bodies:
            idx = raw_idx if raw_idx >= 0 else len(messages) + raw_idx
            m = messages[idx]
            origin = message_origin(m) or type(m).__name__
            print(f"\n[{idx:02d} {origin}]")
            print(_format_body_preview(m, max_skill_lines=max_skill_lines))


def build_live_request(
    mw: Any,
    state: dict,
    tools: Optional[Sequence[Any]] = None,
    context: Any = None,
    model: str = "demo",
) -> Any:
    """wrap_model_call이 모델 API 직전에 조립한 최종 ModelRequest를 그대로 반환합니다."""
    req = ModelRequest(
        messages=state["messages"],
        model=model,
        tool_choice="auto",
        model_settings={},
        state=state,
        tools=list(tools or []),
        runtime=SimpleNamespace(context=context, config=None, execution_info=None),
    )
    return mw.wrap_model_call(req, lambda r: r)


def simulate_turn(
    mw: Any,
    state: dict,
    label: str,
    prev_messages: Optional[Sequence[Any]] = None,
    tools: Optional[Sequence[Any]] = None,
    context: Any = None,
    show_bodies: Optional[Iterable[int]] = None,
) -> Any:
    """before_model(스킬 Delta · 날짜 변경 알림 저장) + wrap_model_call(전체 메시지 조립) 결과를 출력합니다."""
    runtime = SimpleNamespace(context=context, config=None, execution_info=None)
    update = mw.before_model(state, runtime=runtime) or {}
    added = update.pop("messages", [])
    state.update(update)
    state["messages"] = list(state.get("messages") or []) + added

    out = build_live_request(mw, state, tools or [], context)
    added_indices = list(range(len(out.messages) - len(added), len(out.messages))) if added else []
    body_indices = added_indices if show_bodies is None else show_bodies

    show_prompt_map(
        out.messages,
        f"{label} (전체 {len(out.messages)}개 · 신규 알림 {len(added)}개)",
        tools=out.tools if tools else None,
        prev_messages=prev_messages,
        highlight_indices=added_indices,
        show_bodies=body_indices,
    )
    return out


__all__ = ["show_prompt_map", "build_live_request", "simulate_turn"]
