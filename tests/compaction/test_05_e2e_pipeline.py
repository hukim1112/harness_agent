"""
=============================================================================
Test 05: E2E Compactor Middleware Pipeline & Multi-Turn Integration
=============================================================================
1. create_compactor_middleware (@wrap_model_call) 전체 파이프라인 검증
2. Phase 1 Pre-call Pipeline 실행 순서 (Snip ➔ Micro ➔ Collapse ➔ Auto)
3. Phase 2 413 API Error 발생 시 Reactive Compactor 자동 복구 재시도
4. 대용량 웹 검색 ➔ MicroCompactor 스왑 ➔ 에이전트가 read_file로 스왑 파일 부분 조회하는 흐름
5. 멀티턴 에이전트 통합 시나리오 (Snip, Micro, Collapse, Auto, AmnesiaGuard 복합 발동)
=============================================================================
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from app.middleware.compaction.compactor import create_compactor_middleware
from app.middleware.compaction.amnesia_guard import AmnesiaGuardMiddleware, create_amnesia_guard_middleware


class MockModelRequest:
    """Mock request object for @wrap_model_call middleware"""
    def __init__(self, messages: list):
        self.messages = list(messages)

    def override(self, **kwargs):
        new_req = MockModelRequest(kwargs.get("messages", self.messages))
        return new_req


class TestE2EPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_e2e_pipeline_")
        self.swap_dir = os.path.join(self.test_dir, "swaps")
        os.makedirs(self.swap_dir, exist_ok=True)

        self.sample_code_file = os.path.join(self.test_dir, "app_server.py")
        with open(self.sample_code_file, "w", encoding="utf-8") as f:
            f.write("# App Server v1.0\nfrom fastapi import FastAPI\napp = FastAPI()\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_phase1_sequential_pipeline_execution(self):
        """Snip, Micro, Collapse, Auto가 Phase 1 파이프라인에서 순차적으로 모두 적용되는지 검증"""
        guard = AmnesiaGuardMiddleware()
        guard.track_file_access(self.sample_code_file)
        guard.set_active_plan("Build High-Performance Microservice")

        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 10000
        mock_llm.invoke.return_value = AIMessage(content="Structured 4-Section Summary of prior work")

        compactor_mw = create_compactor_middleware(
            llm=mock_llm,
            threshold_tokens=500,
            amnesia_guard=guard,
            swap_dir=self.swap_dir
        )

        large_doc = "Crawled Doc: " + ("Important API Specification Details\n" * 300)

        raw_messages = [
            SystemMessage(content="System Core L1-L5"),
            # Turn 1: Old tool output (Snip target)
            HumanMessage(content="Turn 1: Check tools"),
            ToolMessage(content="Lengthy initial tool result " * 20, tool_call_id="c1", name="check_tools"),
            AIMessage(content="Turn 1 done"),
            # Turn 2: Giant Web crawl (Micro target)
            HumanMessage(content="Turn 2: Search web"),
            ToolMessage(content=large_doc, tool_call_id="c2", name="web_search"),
            AIMessage(content="Turn 2 done"),
            # Turn 3: 3 consecutive exploration steps (Collapse target)
            HumanMessage(content="Turn 3: Explore workspace"),
            ToolMessage(content="Exploration 1", tool_call_id="e1", name="ls"),
            ToolMessage(content="Exploration 2", tool_call_id="e2", name="grep"),
            ToolMessage(content="Exploration 3", tool_call_id="e3", name="read"),
            AIMessage(content="Turn 3 done"),
            # Turn 4: Final query (Triggers AutoCompactor due to token threshold)
            HumanMessage(content="Turn 4: Final Summary Question"),
        ]

        received_req = None

        def dummy_handler(request):
            nonlocal received_req
            received_req = request
            return AIMessage(content="Final LLM Response")

        req = MockModelRequest(messages=raw_messages)
        res = compactor_mw.wrap_model_call(req, dummy_handler)

        self.assertEqual(res.content, "Final LLM Response")
        self.assertIsNotNone(received_req)

        final_messages = received_req.messages

        # 1. MicroCompactor 검증: swap 파일이 디스크에 생성되었는지
        swap_files = os.listdir(self.swap_dir)
        self.assertGreaterEqual(len(swap_files), 1, "MicroCompactor or Collapse should create swap files")

        # 2. AutoCompactor & AmnesiaGuard 검증: 이전 대화가 요약되고 복원 블록이 주입되었는지
        summary_found = any(isinstance(m, SystemMessage) and "Previous Conversation Summary:" in m.content for m in final_messages)
        amnesia_found = any(isinstance(m, SystemMessage) and "[Compaction Amnesia Guard: Restoring Recent Work Context]" in m.content for m in final_messages)
        
        self.assertTrue(summary_found, "Summary SystemMessage must be generated")
        self.assertTrue(amnesia_found, "AmnesiaGuard recovery SystemMessage must be attached")

        # 3. 최신 유저 메시지가 유지되었는지
        self.assertEqual(final_messages[-1].content, "Turn 4: Final Summary Question")

    def test_02_phase2_reactive_retry_on_413(self):
        """Handler에서 413 에러 발생 시 ReactiveCompactor가 포획하여 20% Tail Slicing 후 자동 재시도하는지 검증"""
        guard = AmnesiaGuardMiddleware()
        guard.track_file_access(self.sample_code_file)

        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 100  # Below auto threshold

        compactor_mw = create_compactor_middleware(
            llm=mock_llm,
            threshold_tokens=5000,
            amnesia_guard=guard,
            swap_dir=self.swap_dir
        )

        call_attempts = 0
        received_requests = []

        def failing_handler(request):
            nonlocal call_attempts, received_requests
            call_attempts += 1
            received_requests.append(request)
            if call_attempts == 1:
                # First call triggers 413
                raise Exception("413 Client Error: Request Entity Too Large (context_length_exceeded)")
            # Second call (retry) succeeds
            return AIMessage(content="Recovered LLM Answer")

        messages = [SystemMessage(content="System Core")]
        for i in range(10):
            messages.append(HumanMessage(content=f"Message {i}"))

        req = MockModelRequest(messages=messages)
        res = compactor_mw.wrap_model_call(req, failing_handler)

        self.assertEqual(call_attempts, 2, "Should attempt 2 calls (1 failure + 1 retry)")
        self.assertEqual(res.content, "Recovered LLM Answer")

        # 재시도된 메시지 검증
        retry_messages = received_requests[1].messages
        reactive_summary_found = any(
            isinstance(m, SystemMessage) and "[Reactive Compact (Silent Withholding)]" in m.content
            for m in retry_messages
        )
        self.assertTrue(reactive_summary_found, "Reactive Summary must be present in retry request")

    def test_03_micro_swap_and_actionable_file_inspection_flow(self):
        """MicroCompactor로 스왑된 파일 경로에서 필요한 부분을 read_file 슬라이스로 읽는 서브 플로우 검증"""
        # 1. 10,000자 대용량 데이터 생성
        large_content = "HEADER: API Reference Guide\n"
        for line_no in range(1, 201):
            if line_no == 150:
                large_content += f"Line {line_no}: CRITICAL_SECRET_KEY = 'super-secret-xyz-2026'\n"
            else:
                large_content += f"Line {line_no}: Regular documentation text payload information...\n"

        from app.middleware.compaction.compactor import MicroCompactor
        micro = MicroCompactor(max_chars=2000, swap_dir=self.swap_dir)

        messages = [
            HumanMessage(content="Fetch large API documentation"),
            ToolMessage(content=large_content, tool_call_id="call_doc_1", name="fetch_doc")
        ]

        compacted, modified = micro.compact(messages)
        self.assertTrue(modified)

        stub_content = str(compacted[1].content)
        self.assertIn("Actionable Hint", stub_content)

        # 2. 에이전트가 힌트에서 swap 파일 경로를 파싱하여 부분 읽기 수행 (Mocking agent action)
        import re
        match = re.search(r"swap_[a-zA-Z0-9]+\.txt", stub_content)
        self.assertIsNotNone(match)
        swap_file_name = match.group(0)
        full_swap_path = os.path.join(self.swap_dir, swap_file_name)

        self.assertTrue(os.path.exists(full_swap_path))

        # 3. read_file로 Line 148 ~ Line 152만 슬라이스 조회
        with open(full_swap_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        sliced_lines = all_lines[147:152]
        sliced_text = "".join(sliced_lines)

        self.assertIn("CRITICAL_SECRET_KEY = 'super-secret-xyz-2026'", sliced_text)
        self.assertLess(len(sliced_text), 500, "Inspecting specific lines takes minimal tokens")


if __name__ == "__main__":
    unittest.main()
