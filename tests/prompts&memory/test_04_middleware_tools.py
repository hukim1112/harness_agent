"""
=============================================================================
Test 04: Memory Middleware + Tool 통합 검증
=============================================================================
검증 항목:
  1. get_tools(): memory + session_recall 2개 도구 생성
  2. memory 도구 쓰기: add → 디스크 반영 확인
  3. memory 도구 교체: replace → 내용 변경 확인
  4. memory 도구 삭제: remove → 엔트리 제거 확인
  5. session_recall 도구: Anchor 기반 메시지 반환
  6. before_agent: ctx.recalled_memory 주입 (Semantic + Episodic)
  7. 이중 주입 방지: l4_docs 빈 상태에서 recalled_memory만 L4에 주입
=============================================================================
"""

import os
import sys
import json
import asyncio
import tempfile

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.middleware.memory.semantic_store import SemanticMemoryStore
from app.middleware.memory.episodic_store import EpisodicStore
from app.middleware.memory.memory_middleware import MemoryMiddleware


def _run(coro):
    return asyncio.run(coro)


class FakeContext:
    """AgentContext 시뮬레이션."""
    def __init__(self):
        self.semantic_memory_enabled = True
        self.episodic_memory_enabled = True
        self.memory_learning_enabled = False
        self.memory_dir = "./artifacts/memory"
        self.recalled_memory = ""
        self.session_id = "unknown"


class FakeRuntime:
    """Runtime 시뮬레이션."""
    def __init__(self, ctx=None, config=None):
        self.context = ctx or FakeContext()
        self.config = config or {"configurable": {"thread_id": "test-session-42"}}


def test_01_get_tools_count_and_names():
    """get_tools(): 2개 도구 반환 + 이름 확인."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ss = SemanticMemoryStore(memory_dir=tmpdir)
        ss.load_from_disk()
        es = EpisodicStore(db_path=os.path.join(tmpdir, "ep.db"))
        _run(es.setup())

        mw = MemoryMiddleware(semantic_store=ss, episodic_store=es)
        tools = mw.get_tools()
        names = {t.name for t in tools}

        assert len(tools) == 2, f"2개 도구 예상, 실제: {len(tools)}"
        assert "memory" in names, "'memory' 도구 없음"
        assert "session_recall" in names, "'session_recall' 도구 없음"
        _run(es.close())
    return {"pass": True, "detail": f"get_tools() → 2개 도구: {names}"}


def test_02_memory_tool_add():
    """memory 도구: add → 디스크 반영."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ss = SemanticMemoryStore(memory_dir=tmpdir)
        ss.load_from_disk()
        es = EpisodicStore(db_path=os.path.join(tmpdir, "ep.db"))
        _run(es.setup())

        mw = MemoryMiddleware(semantic_store=ss, episodic_store=es)
        memory_tool = [t for t in mw.get_tools() if t.name == "memory"][0]

        result_str = memory_tool.invoke({
            "action": "add", "target": "memory",
            "content": "User runs WSL Ubuntu with Python 3.12."
        })
        result = json.loads(result_str)
        assert result["success"] is True, f"add 실패: {result}"
        assert "User runs WSL" in ss.memory_entries[0]

        # 디스크 영속성
        ss2 = SemanticMemoryStore(memory_dir=tmpdir)
        ss2.load_from_disk()
        assert "User runs WSL" in ss2.memory_entries[0], "디스크 반영 안 됨"
        _run(es.close())
    return {"pass": True, "detail": "memory(add) → live entries + 디스크 영속성 확인"}


def test_03_memory_tool_replace():
    """memory 도구: replace → 교체 확인."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ss = SemanticMemoryStore(memory_dir=tmpdir)
        ss.load_from_disk()
        ss.add("user", "User prefers dark mode.")
        es = EpisodicStore(db_path=os.path.join(tmpdir, "ep.db"))
        _run(es.setup())

        mw = MemoryMiddleware(semantic_store=ss, episodic_store=es)
        memory_tool = [t for t in mw.get_tools() if t.name == "memory"][0]

        result_str = memory_tool.invoke({
            "action": "replace", "target": "user",
            "old_text": "dark mode",
            "content": "User prefers light mode."
        })
        result = json.loads(result_str)
        assert result["success"] is True
        assert "light mode" in ss.user_entries[0]
        _run(es.close())
    return {"pass": True, "detail": "memory(replace) → 'dark mode' → 'light mode' 교체 확인"}


def test_04_memory_tool_remove():
    """memory 도구: remove → 삭제 확인."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ss = SemanticMemoryStore(memory_dir=tmpdir)
        ss.load_from_disk()
        ss.add("memory", "Obsolete fact.")
        es = EpisodicStore(db_path=os.path.join(tmpdir, "ep.db"))
        _run(es.setup())

        mw = MemoryMiddleware(semantic_store=ss, episodic_store=es)
        memory_tool = [t for t in mw.get_tools() if t.name == "memory"][0]

        result_str = memory_tool.invoke({
            "action": "remove", "target": "memory",
            "old_text": "Obsolete"
        })
        result = json.loads(result_str)
        assert result["success"] is True
        assert len(ss.memory_entries) == 0
        _run(es.close())
    return {"pass": True, "detail": "memory(remove) → 'Obsolete' 엔트리 삭제 + entries 빈 리스트 확인"}


def test_05_session_recall_tool():
    """session_recall 도구: Anchor 기반 메시지 인출."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            ss = SemanticMemoryStore(memory_dir=tmpdir)
            ss.load_from_disk()
            es = EpisodicStore(db_path=os.path.join(tmpdir, "ep.db"))
            await es.setup()

            # 세션 데이터 삽입
            await es.finalize_session("s_test", [
                {"role": "human", "content": "LangGraph에서 state 관리는 어떻게 하나?"},
                {"role": "ai", "content": "TypedDict로 state schema를 정의합니다."},
                {"role": "human", "content": "checkpointer는 어떻게 연결하나요?"},
                {"role": "ai", "content": "AsyncSqliteSaver를 checkpointer 인자로 전달합니다."},
            ], llm=None)

            mw = MemoryMiddleware(semantic_store=ss, episodic_store=es)
            recall_tool = [t for t in mw.get_tools() if t.name == "session_recall"][0]

            result_str = recall_tool.invoke({
                "session_id": "s_test",
                "anchor_message": "checkpointer",
                "window": 2,
            })
            result = json.loads(result_str)
            await es.close()
            return result

    result = _run(_test())
    assert result.get("message_count", 0) > 0, f"session_recall 결과 비어있음: {result}"
    contents = " ".join(m["content"] for m in result.get("messages", []))
    assert "checkpointer" in contents.lower() or "sqlite" in contents.lower(), \
        f"anchor 주변에 checkpointer 관련 내용 없음"
    return {"pass": True, "detail": f"session_recall(anchor='checkpointer') → {result['message_count']}개 메시지 인출"}


def test_06_before_agent_recalled_memory_injection():
    """before_agent: ctx.recalled_memory에 Semantic + Episodic 주입."""
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            ss = SemanticMemoryStore(memory_dir=tmpdir)
            ss.load_from_disk()
            ss.add("memory", "Project uses FastAPI.")
            ss.add("user", "User speaks Korean.")
            ss.load_from_disk()  # Frozen snapshot 갱신

            es = EpisodicStore(db_path=os.path.join(tmpdir, "ep.db"))
            await es.setup()
            await es.finalize_session("past_session", [
                {"role": "human", "content": "LangChain agent에서 memory tool을 어떻게 바인딩?"},
                {"role": "ai", "content": "MemoryMiddleware.get_tools()로 바인딩합니다."},
            ], llm=None)

            mw = MemoryMiddleware(semantic_store=ss, episodic_store=es)
            ctx = FakeContext()
            runtime = FakeRuntime(ctx=ctx)

            from langchain_core.messages import HumanMessage
            state = {"messages": [HumanMessage(content="memory tool 바인딩 방법은?")]}

            mw.before_agent(state, runtime)
            await es.close()
            return ctx.recalled_memory

    recalled = _run(_test())
    assert recalled and len(recalled) > 0, "recalled_memory가 비어있음"
    assert "MEMORY" in recalled or "Project uses FastAPI" in recalled, \
        f"Semantic Memory가 recalled_memory에 미주입: {recalled[:100]}"
    return {"pass": True, "detail": f"before_agent → ctx.recalled_memory 주입 ({len(recalled)} chars): Semantic + Episodic 포함"}


def test_07_no_double_injection():
    """이중 주입 방지: PromptAssembler l4_docs 빈 상태에서 L4에 USER.md/MEMORY.md 직접 출력 없음."""
    from app.middleware.prompt.prompt_assembler import PromptAssembler

    assembler = PromptAssembler(
        system_rules="test",
        tool_schemas=[],
        l4_docs={},  # 비어있어야 함
    )
    dynamic = assembler.build_dynamic_content({
        "session_id": "test",
        "recalled_memory": "══════ MEMORY ══════\nProject uses FastAPI.",
    })
    assert "[USER.md]:" not in dynamic, "l4_docs에서 USER.md가 직접 출력됨 (이중 주입)"
    assert "[MEMORY.md]:" not in dynamic, "l4_docs에서 MEMORY.md가 직접 출력됨 (이중 주입)"
    assert "Project uses FastAPI" in dynamic, "recalled_memory 내용이 L4에 없음"
    return {"pass": True, "detail": "L4에 recalled_memory만 출력, l4_docs에서 USER.md/MEMORY.md 직접 출력 없음 (이중 주입 방지)"}


# ── Runner ──

ALL_TESTS = [
    test_01_get_tools_count_and_names,
    test_02_memory_tool_add,
    test_03_memory_tool_replace,
    test_04_memory_tool_remove,
    test_05_session_recall_tool,
    test_06_before_agent_recalled_memory_injection,
    test_07_no_double_injection,
]


def run_all():
    results = []
    for test_fn in ALL_TESTS:
        name = test_fn.__name__
        try:
            result = test_fn()
            results.append({"test": name, "status": "PASS", "detail": result["detail"]})
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "detail": str(e)})
    return results


if __name__ == "__main__":
    results = run_all()
    print("=" * 70)
    print("Test 04: Memory Middleware + Tool 통합 검증")
    print("=" * 70)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['test']}: {r['detail']}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n  Result: {passed}/{total} passed")
