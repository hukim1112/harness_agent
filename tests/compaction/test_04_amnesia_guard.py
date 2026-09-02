"""
=============================================================================
Test 04: AmnesiaGuard & 도구 인터셉터 단위 테스트
=============================================================================
1. 최근 파일 접근 경로 LRU 추적 및 max_restore_files 제한
2. 활성 계획(Active Plan) 보존 및 갱신
3. 디스크 실제 파일 내용과 계획을 담은 복원 SystemMessage 생성
4. @wrap_tool_call 인터셉터를 통한 도구 실행 인자(file_path, plan 등) 자동 캡처
5. AutoCompactor 및 ReactiveCompactor와의 복원 블록 결합 검증
=============================================================================
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.middleware.compaction.amnesia_guard import AmnesiaGuardMiddleware, create_amnesia_guard_middleware
from app.middleware.compaction.compactor import AutoCompactor, ReactiveCompactor


class MockToolRequest:
    """Mock request passed into @wrap_tool_call handler"""
    def __init__(self, name: str, args: dict):
        self.tool_call = {"name": name, "args": args, "id": "call_123"}


class TestAmnesiaGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_amnesia_")
        self.sample_file_1 = os.path.join(self.test_dir, "auth.py")
        self.sample_file_2 = os.path.join(self.test_dir, "models.py")

        with open(self.sample_file_1, "w", encoding="utf-8") as f:
            f.write("def verify_jwt():\n    return True\n")

        with open(self.sample_file_2, "w", encoding="utf-8") as f:
            f.write("class UserModel:\n    name: str\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_track_file_access_lru(self):
        """최근 파일 경로가 LRU(가장 최근 접근한 파일이 끝으로 이동)로 관리되는지 검증"""
        guard = AmnesiaGuardMiddleware(max_restore_files=3)

        guard.track_file_access("a.py")
        guard.track_file_access("b.py")
        guard.track_file_access("a.py")  # Re-access a.py

        self.assertEqual(guard.recent_files, [os.path.normpath("b.py"), os.path.normpath("a.py")])

    def test_02_track_file_access_max_limit(self):
        """max_restore_files(예: 2개)를 초과할 경우 오래된 파일이 삭제되는지 검증"""
        guard = AmnesiaGuardMiddleware(max_restore_files=2)

        guard.track_file_access("f1.py")
        guard.track_file_access("f2.py")
        guard.track_file_access("f3.py")

        self.assertEqual(len(guard.recent_files), 2)
        self.assertEqual(guard.recent_files, [os.path.normpath("f2.py"), os.path.normpath("f3.py")])

    def test_03_set_active_plan(self):
        """활성 계획 텍스트 보존 및 갱신 검증"""
        guard = AmnesiaGuardMiddleware()
        self.assertIsNone(guard.active_plan)

        guard.set_active_plan("Step 1: Write Tests\nStep 2: Implement Code")
        self.assertEqual(guard.active_plan, "Step 1: Write Tests\nStep 2: Implement Code")

    def test_04_create_recovery_attachments_files_and_plan(self):
        """디스크 실제 파일 내용과 활성 계획이 SystemMessage 복원 블록으로 생성되는지 검증"""
        guard = AmnesiaGuardMiddleware(max_restore_files=5)
        guard.track_file_access(self.sample_file_1)
        guard.track_file_access(self.sample_file_2)
        guard.set_active_plan("1. Implement JWT Auth\n2. Add SQLite Storage")

        attachments = guard.create_recovery_attachments()
        self.assertEqual(len(attachments), 1)

        msg = attachments[0]
        self.assertIsInstance(msg, SystemMessage)
        content = msg.content

        self.assertIn("[Compaction Amnesia Guard: Restoring Recent Work Context]", content)
        self.assertIn("=== Active Plan ===", content)
        self.assertIn("1. Implement JWT Auth", content)
        self.assertIn("=== Recently Modified/Accessed Files ===", content)
        self.assertIn("File: " + os.path.normpath(self.sample_file_1), content)
        self.assertIn("def verify_jwt():", content)
        self.assertIn("File: " + os.path.normpath(self.sample_file_2), content)
        self.assertIn("class UserModel:", content)

    def test_05_amnesia_tool_interceptor_wrap_tool_call(self):
        """@wrap_tool_call 인터셉터가 write_file, update_plan 도구 호출 시 인자를 자동 캡처하는지 검증"""
        guard = AmnesiaGuardMiddleware(max_restore_files=5)
        interceptor = create_amnesia_guard_middleware(guard)

        # 1. Mock file write tool call
        req_file = MockToolRequest(name="write_file", args={"file_path": self.sample_file_1, "content": "hello"})
        interceptor.wrap_tool_call(req_file, lambda r: "file written")

        self.assertEqual(guard.recent_files, [os.path.normpath(self.sample_file_1)])

        # 2. Mock plan update tool call
        req_plan = MockToolRequest(name="update_plan", args={"plan": "Execute Step A and Step B"})
        interceptor.wrap_tool_call(req_plan, lambda r: "plan updated")

        self.assertEqual(guard.active_plan, "Execute Step A and Step B")

    def test_06_amnesia_guard_integrated_with_auto_compactor(self):
        """AutoCompactor 실행 시 AmnesiaGuard의 복원 블록이 요약 메시지 바로 뒤에 주입되는지 검증"""
        guard = AmnesiaGuardMiddleware()
        guard.track_file_access(self.sample_file_1)
        guard.set_active_plan("Refactor auth system")

        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 10000
        mock_llm.invoke.return_value = AIMessage(content="Summary of previous turns")

        auto = AutoCompactor(llm=mock_llm, threshold_tokens=1000, amnesia_guard=guard)

        messages = [
            SystemMessage(content="L1 System"),
            HumanMessage(content="Turn 1"),
            AIMessage(content="Turn 1 Resp"),
            HumanMessage(content="Turn 2 Question"),
        ]

        compacted, modified = auto.compact_if_needed(messages)
        self.assertTrue(modified)

        # Structure: SystemMessage + Summary SystemMessage + Amnesia Recovery SystemMessage + Latest HumanMessage = 4 messages
        self.assertEqual(len(compacted), 4)
        self.assertEqual(compacted[0].content, "L1 System")
        self.assertIn("Previous Conversation Summary:", compacted[1].content)
        self.assertIn("[Compaction Amnesia Guard: Restoring Recent Work Context]", compacted[2].content)
        self.assertIn("def verify_jwt():", compacted[2].content)
        self.assertEqual(compacted[3].content, "Turn 2 Question")

    def test_07_amnesia_guard_integrated_with_reactive_compactor(self):
        """ReactiveCompactor 실행 시 AmnesiaGuard의 복원 블록이 정상 주입되는지 검증"""
        guard = AmnesiaGuardMiddleware()
        guard.set_active_plan("Emergency Recovery Plan")

        reactive = ReactiveCompactor(slice_ratio=0.20, amnesia_guard=guard)

        messages = [SystemMessage(content="Core System")]
        for i in range(10):
            messages.append(HumanMessage(content=f"Msg {i}"))

        recovered = reactive.handle_overflow(messages)
        # Structure: System + Reactive Summary + Amnesia Recovery + 8 dialogue messages = 11 messages
        self.assertEqual(len(recovered), 11)
        self.assertIn("[Compaction Amnesia Guard: Restoring Recent Work Context]", recovered[2].content)
        self.assertIn("Emergency Recovery Plan", recovered[2].content)


if __name__ == "__main__":
    unittest.main()
