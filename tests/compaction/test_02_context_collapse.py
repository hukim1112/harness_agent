"""
=============================================================================
Test 02: ContextCollapse 단위 테스트
=============================================================================
1. 3개 이상의 연속 탐색/조회 스텝(Tool & Thought) 1개 SystemMessage로 접기
2. 2개 이하의 짧은 도구 호출은 접히지 않고 원본 유지
3. AIMessage(tool_calls)와 ToolMessage가 교차하는 리서치 시퀀스 그룹화
4. collapse_snap_*.txt 디스크 백업 및 전체 원문 트랜스크립트 보존 검증
5. 접히는 블록 앞뒤의 일반 대화(Human/AI) 무손실 보존
=============================================================================
"""

import os
import shutil
import tempfile
import unittest
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from app.middleware.compaction.compactor import ContextCollapse


class TestContextCollapse(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_collapse_")
        self.swap_dir = os.path.join(self.test_dir, "swaps")
        os.makedirs(self.swap_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_collapse_3_consecutive_steps(self):
        """3개의 연속된 ToolMessage가 1개의 Collapsed SystemMessage로 접히는지 검증"""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            HumanMessage(content="Start investigation"),
            ToolMessage(content="Found 10 items", tool_call_id="c1", name="find_files"),
            ToolMessage(content="Matched 5 lines", tool_call_id="c2", name="grep_code"),
            ToolMessage(content="File contents: ...", tool_call_id="c3", name="read_file"),
            AIMessage(content="Investigation concluded successfully."),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertTrue(modified)
        self.assertEqual(len(compacted), 3, "Should collapse 3 tool messages into 1 system message")

        collapsed_msg = compacted[1]
        self.assertIsInstance(collapsed_msg, SystemMessage)
        self.assertIn("Context Collapsed: 3 research steps", collapsed_msg.content)
        self.assertIn("find_files", collapsed_msg.content)
        self.assertIn("grep_code", collapsed_msg.content)
        self.assertIn("read_file", collapsed_msg.content)

    def test_02_collapse_less_than_threshold_untouched(self):
        """2개 이하의 도구 호출은 min_consecutive(3) 미만이므로 접히지 않고 원본 유지"""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            HumanMessage(content="Do two tasks"),
            ToolMessage(content="Result 1", tool_call_id="c1", name="tool_1"),
            ToolMessage(content="Result 2", tool_call_id="c2", name="tool_2"),
            AIMessage(content="Finished"),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertFalse(modified)
        self.assertEqual(len(compacted), 4)
        self.assertIsInstance(compacted[1], ToolMessage)
        self.assertIsInstance(compacted[2], ToolMessage)

    def test_03_collapse_mixed_ai_thought_and_tools(self):
        """AIMessage(tool_calls)와 ToolMessage가 교차하는 8단계 리서치 블록 전체 접기 검증"""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            SystemMessage(content="System prompt L1-L5"),
            HumanMessage(content="Refactor the auth module"),
            # 8 consecutive research steps
            AIMessage(content="Looking for auth files", tool_calls=[{"name": "glob", "args": {}, "id": "g1"}]),
            ToolMessage(content="auth/jwt.py, auth/oauth.py", tool_call_id="g1", name="glob"),
            AIMessage(content="Searching token validator", tool_calls=[{"name": "grep", "args": {}, "id": "g2"}]),
            ToolMessage(content="def validate_token(): ...", tool_call_id="g2", name="grep"),
            AIMessage(content="Reading jwt implementation", tool_calls=[{"name": "read_file", "args": {}, "id": "g3"}]),
            ToolMessage(content="class JWTHandler: ...", tool_call_id="g3", name="read_file"),
            AIMessage(content="Checking syntax", tool_calls=[{"name": "py_check", "args": {}, "id": "g4"}]),
            ToolMessage(content="Syntax OK", tool_call_id="g4", name="py_check"),
            # Next normal response
            AIMessage(content="I have analyzed the auth module. Here is the refactoring plan:"),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertTrue(modified)

        # Structure: SystemMessage + HumanMessage + Collapsed SystemMessage + AIMessage
        self.assertEqual(len(compacted), 4)
        collapsed_node = compacted[2]
        self.assertIsInstance(collapsed_node, SystemMessage)
        self.assertIn("Context Collapsed: 8 research steps", collapsed_node.content)
        self.assertIn("glob, grep, py_check, read_file", collapsed_node.content)

    def test_04_collapse_snapshot_disk_backup(self):
        """접힌 8단계의 원본 트랜스크립트가 collapse_snap_*.txt에 온전히 백업되는지 검증"""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            ToolMessage(content="Secret Key 12345", tool_call_id="c1", name="get_key"),
            ToolMessage(content="Database Config Host: localhost", tool_call_id="c2", name="get_db"),
            ToolMessage(content="Port: 5432", tool_call_id="c3", name="get_port"),
        ]

        compacted, _ = collapse.compact(messages)
        content = compacted[0].content

        self.assertIn("Actionable Hint", content)
        self.assertIn("collapse_snap_", content)
        snap_files = [f for f in os.listdir(self.swap_dir) if f.startswith("collapse_snap_")]
        self.assertEqual(len(snap_files), 1, "Should create 1 collapse snapshot file")

        snap_path = os.path.join(self.swap_dir, snap_files[0])
        with open(snap_path, "r", encoding="utf-8") as sf:
            raw_log = sf.read()

        self.assertIn("Secret Key 12345", raw_log)
        self.assertIn("Database Config Host: localhost", raw_log)
        self.assertIn("Port: 5432", raw_log)

    def test_05_collapse_preserves_surrounding_dialogue(self):
        """연속 탐색 구간 앞뒤의 일반 사용자 질의 및 AI 응답이 정확히 보존되는지 검증"""
        collapse = ContextCollapse(min_consecutive=3, swap_dir=self.swap_dir)

        messages = [
            HumanMessage(content="First Question"),
            AIMessage(content="First Answer"),
            HumanMessage(content="Deep Investigation"),
            ToolMessage(content="Step 1", tool_call_id="1", name="t1"),
            ToolMessage(content="Step 2", tool_call_id="2", name="t2"),
            ToolMessage(content="Step 3", tool_call_id="3", name="t3"),
            AIMessage(content="Investigation Done"),
            HumanMessage(content="Final Question"),
        ]

        compacted, modified = collapse.compact(messages)
        self.assertTrue(modified)

        self.assertEqual(compacted[0].content, "First Question")
        self.assertEqual(compacted[1].content, "First Answer")
        self.assertEqual(compacted[2].content, "Deep Investigation")
        self.assertIsInstance(compacted[3], SystemMessage)
        self.assertEqual(compacted[4].content, "Investigation Done")
        self.assertEqual(compacted[5].content, "Final Question")


if __name__ == "__main__":
    unittest.main()
