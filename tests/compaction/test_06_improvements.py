"""
===============================================================================
Test 06: Improvement Verification Tests
===============================================================================
통합 감사 보고서 D1~D25 결함 수정 검증 전용 테스트.
각 Fix가 의도대로 동작하는지 개별 검증합니다.

- Fix 1: 파이프라인 순서 교정 (Snip→Micro) + MicroCompactor Idempotency
- Fix 2: ContextCollapse 변경성 도구 차단 + tool_call_id 보존
- Fix 3: ReactiveCompactor 턴 경계 슬라이싱 (AI-Tool 쌍 보존)
- Fix 4: AutoCompactor Collapse SystemMessage 분류 개선
- Fix 5: AmnesiaGuard 파일 트리밍 + list steps 지원
- Fix 6: CompactorMiddleware(AgentMiddleware) + awrap_model_call
- Fix 7: import time 모듈 상단 + steps list 타입
===============================================================================
"""

import os
import sys
import shutil
import asyncio
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain.agents.middleware import AgentMiddleware

from app.middleware.compaction.compactor import (
    SnipCompactor,
    MicroCompactor,
    ContextCollapse,
    AutoCompactor,
    ReactiveCompactor,
    CompactorMiddleware,
    create_compactor_middleware,
    UNSAFE_TO_COLLAPSE_TOOLS,
)
from app.middleware.compaction.amnesia_guard import (
    AmnesiaGuardMiddleware,
    create_amnesia_guard_middleware,
)


class TestFix1PipelineOrderAndIdempotency(unittest.TestCase):
    """Fix 1: 파이프라인 순서 교정 + MicroCompactor Idempotency 검증"""

    def setUp(self):
        self.swap_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.swap_dir, ignore_errors=True)

    def test_01_snip_runs_before_micro_preserves_actionable_hint(self):
        """Snip이 먼저 오래된 대형 출력을 축약하고, Micro는 최근 턴의 대형 출력만 스왑.
        Micro 스텁의 Actionable Hint가 Snip에 의해 파괴되지 않음을 검증."""
        large_old_output = "Old large data " * 500   # ~7500 chars (Turn 1, old)
        large_recent_output = "Recent large data " * 500  # ~9000 chars (Turn 3, recent)

        messages = [
            SystemMessage(content="System"),
            # Turn 1 (old — should be snipped)
            HumanMessage(content="Turn 1"),
            ToolMessage(content=large_old_output, tool_call_id="c1", name="web_search"),
            AIMessage(content="Turn 1 done"),
            # Turn 2
            HumanMessage(content="Turn 2"),
            AIMessage(content="Turn 2 done"),
            # Turn 3 (recent — should be micro-swapped with hint)
            HumanMessage(content="Turn 3"),
            ToolMessage(content=large_recent_output, tool_call_id="c3", name="read_file"),
            AIMessage(content="Turn 3 done"),
            # Turn 4 (latest)
            HumanMessage(content="Turn 4"),
        ]

        snip = SnipCompactor(age_threshold=2)
        micro = MicroCompactor(max_chars=5000, swap_dir=self.swap_dir)

        # Pipeline order: Snip → Micro
        msgs, _ = snip.compact(messages)
        msgs, _ = micro.compact(msgs)

        # Turn 1's old large output should be SNIPPED (1-line stub, no disk swap)
        turn1_tool = msgs[2]
        self.assertIn("[Tool result snipped:", turn1_tool.content)
        self.assertNotIn("microcompacted to disk", turn1_tool.content)

        # Turn 3's recent large output should be MICRO-SWAPPED with Actionable Hint
        turn3_tool = msgs[7]
        self.assertIn("microcompacted to disk:", turn3_tool.content)
        self.assertIn("Actionable Hint", turn3_tool.content)

    def test_02_micro_idempotency_skips_already_swapped(self):
        """이미 스왑된 스텁은 MicroCompactor가 재스왑하지 않음 (idempotency)."""
        already_swapped_stub = (
            "[Output (15000 chars) microcompacted to disk: ./swaps/swap_abc123.txt]\n"
            "💡 Actionable Hint: Use `read_file` or `grep_search` on './swaps/swap_abc123.txt'."
        )
        messages = [
            ToolMessage(content=already_swapped_stub, tool_call_id="c1", name="web_search"),
            ToolMessage(content="Short result", tool_call_id="c2", name="ls"),
        ]

        micro = MicroCompactor(max_chars=5000, swap_dir=self.swap_dir)
        compacted, modified = micro.compact(messages)

        # Should NOT be modified — the stub is already swapped
        self.assertFalse(modified)
        self.assertEqual(compacted[0].content, already_swapped_stub)
        # No new swap files should be created
        swap_files = [f for f in os.listdir(self.swap_dir) if f.startswith("swap_")]
        self.assertEqual(len(swap_files), 0)


class TestFix2ContextCollapseFiltering(unittest.TestCase):
    """Fix 2: ContextCollapse 변경성 도구 차단 + tool_call_id 보존 검증"""

    def setUp(self):
        self.swap_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.swap_dir, ignore_errors=True)

    def test_01_blocks_unsafe_write_tools(self):
        """write_file이 포함된 시퀀스는 접히지 않음."""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            HumanMessage(content="Start"),
            ToolMessage(content="Read OK", tool_call_id="c1", name="read_file"),
            ToolMessage(content="Written", tool_call_id="c2", name="write_file"),  # UNSAFE
            ToolMessage(content="Grepped", tool_call_id="c3", name="grep_search"),
            AIMessage(content="Done"),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertFalse(modified, "Groups with unsafe tools must NOT be collapsed")
        self.assertEqual(len(compacted), len(messages))

    def test_02_blocks_unsafe_run_command(self):
        """run_command가 포함된 시퀀스는 접히지 않음."""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "c1"}]),
            ToolMessage(content="File content", tool_call_id="c1", name="read_file"),
            AIMessage(content="", tool_calls=[{"name": "run_command", "args": {}, "id": "c2"}]),
            ToolMessage(content="Output", tool_call_id="c2", name="run_command"),  # UNSAFE
            AIMessage(content="", tool_calls=[{"name": "grep_search", "args": {}, "id": "c3"}]),
            ToolMessage(content="Found", tool_call_id="c3", name="grep_search"),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertFalse(modified, "Groups with run_command must NOT be collapsed")

    def test_03_allows_safe_read_only_tools(self):
        """모든 도구가 읽기 전용이면 정상적으로 접힘."""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            HumanMessage(content="Investigate"),
            ToolMessage(content="Files found", tool_call_id="c1", name="list_dir"),
            ToolMessage(content="Matches", tool_call_id="c2", name="grep_search"),
            ToolMessage(content="Content", tool_call_id="c3", name="read_file"),
            AIMessage(content="Analysis complete"),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertTrue(modified)
        collapsed_msg = [m for m in compacted if isinstance(m, SystemMessage) and "[Context Collapsed:" in m.content]
        self.assertEqual(len(collapsed_msg), 1)

    def test_04_preserves_tool_call_ids_in_metadata(self):
        """접힌 SystemMessage의 additional_kwargs에 tool_call_ids가 보존됨."""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            ToolMessage(content="R1", tool_call_id="call_abc", name="list_dir"),
            ToolMessage(content="R2", tool_call_id="call_def", name="grep_search"),
            ToolMessage(content="R3", tool_call_id="call_ghi", name="read_file"),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertTrue(modified)

        collapsed = compacted[0]
        self.assertIsInstance(collapsed, SystemMessage)
        ids = collapsed.additional_kwargs.get("collapsed_tool_call_ids", [])
        self.assertEqual(ids, ["call_abc", "call_def", "call_ghi"])


class TestFix3ReactiveCompactorTurnBoundary(unittest.TestCase):
    """Fix 3: ReactiveCompactor 턴 경계 슬라이싱 검증 (AI-Tool 쌍 보존)"""

    def test_01_no_orphan_tool_messages_after_slicing(self):
        """슬라이싱 후 고아 ToolMessage(대응 AIMessage 없는)가 없어야 함."""
        reactive = ReactiveCompactor(slice_ratio=0.30)

        # 현실적인 메시지 시퀀스: AI(tool_calls) + ToolMessage 쌍
        messages = [
            SystemMessage(content="System"),
            # Turn 1
            HumanMessage(content="Turn 1"),
            AIMessage(content="", tool_calls=[{"name": "grep", "args": {}, "id": "c1"}]),
            ToolMessage(content="Found 5", tool_call_id="c1", name="grep"),
            AIMessage(content="Turn 1 response"),
            # Turn 2
            HumanMessage(content="Turn 2"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "c2"}]),
            ToolMessage(content="File data", tool_call_id="c2", name="read_file"),
            AIMessage(content="Turn 2 response"),
            # Turn 3
            HumanMessage(content="Turn 3"),
            AIMessage(content="Turn 3 direct response"),
        ]

        recovered = reactive.handle_overflow(messages)

        # 결과에서 ToolMessage가 있으면, 바로 앞에 대응하는 AIMessage(tool_calls)가 있어야 함
        non_system = [m for m in recovered if not isinstance(m, SystemMessage)]
        for i, msg in enumerate(non_system):
            if isinstance(msg, ToolMessage):
                # 앞에 AIMessage(tool_calls)가 있어야 함
                preceding = non_system[i - 1] if i > 0 else None
                self.assertIsInstance(preceding, AIMessage, 
                    f"ToolMessage at index {i} has no preceding AIMessage")
                self.assertTrue(getattr(preceding, "tool_calls", None),
                    f"AIMessage before ToolMessage at index {i} has no tool_calls")

    def test_02_slices_at_human_message_boundary(self):
        """HumanMessage 경계에서 정확히 절단됨을 검증."""
        reactive = ReactiveCompactor(slice_ratio=0.30)

        messages = [
            SystemMessage(content="System"),
            # Turn 1
            HumanMessage(content="Turn 1"),
            AIMessage(content="R1"),
            # Turn 2
            HumanMessage(content="Turn 2"),
            AIMessage(content="R2"),
            # Turn 3
            HumanMessage(content="Turn 3"),
            AIMessage(content="R3"),
        ]

        recovered = reactive.handle_overflow(messages)
        # 3 turns, 30% = 0.9 → max(1, 0) = 1 turn sliced
        # Turn boundary at index 1 (Turn 2's HumanMessage)
        # Remaining: Turn 2 + Turn 3

        non_system = [m for m in recovered if not isinstance(m, SystemMessage)]
        # First non-system message should be a HumanMessage (turn boundary)
        first_dialogue = non_system[0]
        self.assertIsInstance(first_dialogue, HumanMessage)
        self.assertIn("Turn 2", first_dialogue.content)


class TestFix4AutoCompactorSystemClassification(unittest.TestCase):
    """Fix 4: AutoCompactor가 Collapse SystemMessage를 요약 대상에 포함시키는지 검증."""

    def test_01_collapse_msg_included_in_summary_not_preserved_at_top(self):
        """Collapse 메시지는 dialogue로 분류되어 요약 대상에 포함.
        L1-L5 원본 시스템 프롬프트만 최상단에 보존."""
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages = MagicMock(return_value=10000)
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="Summary of conversation"))

        auto = AutoCompactor(llm=mock_llm, threshold_tokens=500)

        messages = [
            SystemMessage(content="[L1-L5] System Identity"),
            HumanMessage(content="Turn 1"),
            AIMessage(content="Turn 1 response"),
            SystemMessage(content="[Context Collapsed: 5 research steps (grep_search, read_file) performed in workspace]"),
            HumanMessage(content="Turn 2"),
            AIMessage(content="Turn 2 response"),
            HumanMessage(content="Latest question"),
        ]

        compacted, modified = auto.compact_if_needed(messages)
        self.assertTrue(modified)

        # L1-L5 시스템 프롬프트만 맨 앞에 보존
        self.assertEqual(compacted[0].content, "[L1-L5] System Identity")

        # Collapse SystemMessage는 보존되지 않음 (dialogue에 포함되어 요약됨)
        collapse_preserved = [m for m in compacted if isinstance(m, SystemMessage) 
                             and "[Context Collapsed:" in m.content]
        self.assertEqual(len(collapse_preserved), 0, 
            "Collapse SystemMessage must NOT be preserved — it should be summarized")

        # Summary가 생성됨
        summary = [m for m in compacted if isinstance(m, SystemMessage) 
                  and "Previous Conversation Summary:" in m.content]
        self.assertEqual(len(summary), 1)

    def test_02_original_system_prompt_preserved(self):
        """L1-L5 시스템 프롬프트는 요약되지 않고 원본 보존."""
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages = MagicMock(return_value=10000)
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="Summary"))

        auto = AutoCompactor(llm=mock_llm, threshold_tokens=500)

        messages = [
            SystemMessage(content="You are a helpful AI assistant."),
            SystemMessage(content="Current working directory: /workspace"),
            HumanMessage(content="Q1"),
            AIMessage(content="A1"),
            HumanMessage(content="Q2"),
        ]

        compacted, _ = auto.compact_if_needed(messages)

        # 두 개의 원본 시스템 프롬프트 모두 보존
        preserved_system = [m for m in compacted if isinstance(m, SystemMessage) 
                           and not m.content.startswith("Previous Conversation Summary:")]
        self.assertEqual(len(preserved_system), 2)
        self.assertEqual(preserved_system[0].content, "You are a helpful AI assistant.")
        self.assertEqual(preserved_system[1].content, "Current working directory: /workspace")


class TestFix5AmnesiaGuardTrimming(unittest.TestCase):
    """Fix 5: AmnesiaGuard 파일 트리밍 + list steps 지원 검증"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_large_file_trimmed_to_max_chars(self):
        """대형 파일이 max_file_chars 이내로 트리밍됨."""
        # 500줄짜리 대형 파일 생성
        large_file = os.path.join(self.tmp_dir, "large_module.py")
        lines = [f"def function_{i}():\n    return {i}\n" for i in range(500)]
        with open(large_file, "w") as f:
            f.write("\n".join(lines))

        guard = AmnesiaGuardMiddleware(max_restore_files=5, max_file_chars=3000)
        guard.track_file_access(large_file)

        attachments = guard.create_recovery_attachments()
        self.assertEqual(len(attachments), 1)

        recovery_text = attachments[0].content
        # 전체 파일보다 훨씬 작아야 함
        original_size = os.path.getsize(large_file)
        self.assertLess(len(recovery_text), original_size)
        # Head/Tail 트리밍 마커가 존재해야 함
        self.assertIn("lines omitted", recovery_text)
        # Actionable Hint가 포함되어야 함
        self.assertIn("read_file", recovery_text)

    def test_02_small_file_not_trimmed(self):
        """작은 파일은 트리밍 없이 전체 포함."""
        small_file = os.path.join(self.tmp_dir, "config.py")
        with open(small_file, "w") as f:
            f.write("API_KEY = 'test'\nDEBUG = True\n")

        guard = AmnesiaGuardMiddleware(max_restore_files=5, max_file_chars=3000)
        guard.track_file_access(small_file)

        attachments = guard.create_recovery_attachments()
        recovery_text = attachments[0].content
        self.assertIn("API_KEY = 'test'", recovery_text)
        self.assertNotIn("lines omitted", recovery_text)

    def test_03_list_steps_captured_as_plan(self):
        """list[str] 타입의 steps가 정상적으로 Active Plan으로 캡처됨."""
        guard = AmnesiaGuardMiddleware()
        steps = ["Step 1: Design API", "Step 2: Write tests", "Step 3: Implement"]
        guard.set_active_plan(steps)

        self.assertIsNotNone(guard.active_plan)
        self.assertIn("Step 1: Design API", guard.active_plan)
        self.assertIn("Step 2: Write tests", guard.active_plan)
        self.assertIn("Step 3: Implement", guard.active_plan)
        # 줄바꿈으로 구분
        self.assertEqual(guard.active_plan, "Step 1: Design API\nStep 2: Write tests\nStep 3: Implement")

    def test_04_list_steps_via_interceptor(self):
        """@wrap_tool_call 인터셉터에서 list 타입 steps가 정상 캡처됨."""
        guard = AmnesiaGuardMiddleware()
        interceptor = create_amnesia_guard_middleware(guard)

        class MockToolCallRequest:
            def __init__(self, tool_call):
                self.tool_call = tool_call

        request = MockToolCallRequest({
            "name": "update_plan",
            "args": {"steps": ["Phase 1: Research", "Phase 2: Build", "Phase 3: Test"]},
        })

        def mock_handler(req):
            return "ok"

        interceptor.wrap_tool_call(request, mock_handler)

        self.assertIsNotNone(guard.active_plan)
        self.assertIn("Phase 1: Research", guard.active_plan)
        self.assertIn("Phase 2: Build", guard.active_plan)


class TestFix6CompactorMiddlewareClass(unittest.TestCase):
    """Fix 6: CompactorMiddleware(AgentMiddleware) 클래스 + 비동기 지원 검증"""

    def setUp(self):
        self.swap_dir = tempfile.mkdtemp()
        self.mock_llm = MagicMock()
        self.mock_llm.get_num_tokens_from_messages = MagicMock(return_value=100)

    def tearDown(self):
        shutil.rmtree(self.swap_dir, ignore_errors=True)

    def test_01_is_agent_middleware_subclass(self):
        """CompactorMiddleware는 AgentMiddleware의 서브클래스."""
        mw = create_compactor_middleware(llm=self.mock_llm, swap_dir=self.swap_dir)
        self.assertIsInstance(mw, AgentMiddleware)
        self.assertIsInstance(mw, CompactorMiddleware)

    def test_02_has_wrap_and_awrap_methods(self):
        """wrap_model_call과 awrap_model_call 메서드가 모두 존재."""
        mw = create_compactor_middleware(llm=self.mock_llm, swap_dir=self.swap_dir)
        self.assertTrue(hasattr(mw, "wrap_model_call"))
        self.assertTrue(hasattr(mw, "awrap_model_call"))
        self.assertTrue(callable(mw.wrap_model_call))
        self.assertTrue(callable(mw.awrap_model_call))

    def test_03_sync_wrap_model_call_works(self):
        """동기 wrap_model_call이 정상 동작."""
        mw = create_compactor_middleware(llm=self.mock_llm, swap_dir=self.swap_dir)

        class MockRequest:
            def __init__(self, messages):
                self.messages = messages
            def override(self, messages):
                return MockRequest(messages)

        req = MockRequest([HumanMessage(content="Hello")])
        result = mw.wrap_model_call(req, lambda r: AIMessage(content="Response"))
        self.assertEqual(result.content, "Response")

    def test_04_async_awrap_model_call_works(self):
        """비동기 awrap_model_call이 정상 동작."""
        mw = create_compactor_middleware(llm=self.mock_llm, swap_dir=self.swap_dir)

        class MockRequest:
            def __init__(self, messages):
                self.messages = messages
            def override(self, messages):
                return MockRequest(messages)

        async def run_test():
            req = MockRequest([HumanMessage(content="Hello")])
            
            async def async_handler(r):
                return AIMessage(content="Async Response")
            
            result = await mw.awrap_model_call(req, async_handler)
            return result

        result = asyncio.get_event_loop().run_until_complete(run_test())
        self.assertEqual(result.content, "Async Response")

    def test_05_async_reactive_compactor_on_413(self):
        """비동기 경로에서도 413 에러 시 ReactiveCompactor가 정상 동작."""
        mw = create_compactor_middleware(llm=self.mock_llm, swap_dir=self.swap_dir)

        class MockRequest:
            def __init__(self, messages):
                self.messages = messages
            def override(self, messages):
                return MockRequest(messages)

        call_count = 0

        async def run_test():
            nonlocal call_count
            messages = [SystemMessage(content="System")]
            for i in range(5):
                messages.append(HumanMessage(content=f"Msg {i}"))

            req = MockRequest(messages)

            async def async_handler(r):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("HTTP 413 Request Entity Too Large")
                return AIMessage(content="Retry Success")

            result = await mw.awrap_model_call(req, async_handler)
            return result

        result = asyncio.get_event_loop().run_until_complete(run_test())
        self.assertEqual(result.content, "Retry Success")
        self.assertEqual(call_count, 2)


class TestFix7PipelineOrderInMiddleware(unittest.TestCase):
    """Fix 1+6 통합: CompactorMiddleware 내부 파이프라인 순서가 Snip→Micro→Collapse→Auto."""

    def setUp(self):
        self.swap_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.swap_dir, ignore_errors=True)

    def test_01_pipeline_order_snip_then_micro(self):
        """CompactorMiddleware._run_phase1_pipeline에서 Snip이 Micro보다 먼저 실행.
        오래된 대형 출력은 snip되고, 최근 대형 출력만 micro-swap됨."""
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages = MagicMock(return_value=100)  # Below threshold

        mw = CompactorMiddleware(llm=mock_llm, threshold_tokens=50000, swap_dir=self.swap_dir)

        large_old = "X" * 6000
        large_recent = "Y" * 6000

        messages = [
            # Turn 1 (old)
            HumanMessage(content="T1"),
            ToolMessage(content=large_old, tool_call_id="c1", name="old_tool"),
            AIMessage(content="T1R"),
            # Turn 2
            HumanMessage(content="T2"),
            AIMessage(content="T2R"),
            # Turn 3 (recent)
            HumanMessage(content="T3"),
            ToolMessage(content=large_recent, tool_call_id="c3", name="recent_tool"),
            AIMessage(content="T3R"),
            # Turn 4
            HumanMessage(content="T4"),
        ]

        result = mw._run_phase1_pipeline(messages)

        # Find ToolMessages by content marker (indices may shift due to Collapse)
        snipped_tools = [m for m in result if isinstance(m, ToolMessage) and "[Tool result snipped:" in m.content]
        micro_tools = [m for m in result if isinstance(m, ToolMessage) and "microcompacted to disk:" in m.content]

        # Turn 1's old large tool → snipped (not micro-swapped)
        self.assertGreaterEqual(len(snipped_tools), 1, "Old large ToolMessage must be snipped")
        for st in snipped_tools:
            self.assertNotIn("microcompacted to disk", st.content)

        # Turn 3's recent large tool → micro-swapped with Actionable Hint intact
        self.assertGreaterEqual(len(micro_tools), 1, "Recent large ToolMessage must be micro-swapped")
        for mt in micro_tools:
            self.assertIn("Actionable Hint", mt.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
