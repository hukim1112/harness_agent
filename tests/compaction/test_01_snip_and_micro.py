"""
=============================================================================
Test 01: SnipCompactor & MicroCompactor 단위 테스트
=============================================================================
1. SnipCompactor:
   - 2턴 이전의 오래된 ToolMessage 1줄 스텁 축약
   - 80자 이하의 짧은 ToolMessage 보존
   - tool_call_id 및 name 필드 보존 검증
2. MicroCompactor:
   - 5,000자 초과 대형 도구 결과 디스크 스왑
   - 인라인 Actionable Hint (read_file / grep_search) 포함 검증
   - 5,000자 이하 정상 크기 출력 원본 보존
   - 스왑 파일 디스크 내용 일치성 및 고유성 검증
=============================================================================
"""

import os
import shutil
import tempfile
import unittest
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from app.middleware.compaction.compactor import SnipCompactor, MicroCompactor


class TestSnipAndMicroCompactor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_compactor_")
        self.swap_dir = os.path.join(self.test_dir, "swaps")
        os.makedirs(self.swap_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # SnipCompactor Tests
    # -------------------------------------------------------------------------
    def test_01_snip_compactor_age_threshold(self):
        """Turn 1~4 대화에서 2턴 이전(오래된) ToolMessage만 스텁으로 축약되는지 검증"""
        snip = SnipCompactor(age_threshold=2)

        messages = [
            SystemMessage(content="System prompt"),
            # Turn 1 (Oldest)
            HumanMessage(content="List directory files"),
            AIMessage(content="", tool_calls=[{"name": "list_dir", "args": {}, "id": "call_1"}]),
            ToolMessage(content="FileA.py\nFileB.py\nFileC.py\n" + "x" * 100, tool_call_id="call_1", name="list_dir"),
            AIMessage(content="Found 3 files"),
            # Turn 2 (Middle)
            HumanMessage(content="Read FileA.py"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"path": "FileA.py"}, "id": "call_2"}]),
            ToolMessage(content="def function_a(): pass\n" + "y" * 100, tool_call_id="call_2", name="read_file"),
            AIMessage(content="Read FileA completed"),
            # Turn 3 (Recent)
            HumanMessage(content="Read FileB.py"),
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"path": "FileB.py"}, "id": "call_3"}]),
            ToolMessage(content="def function_b(): pass\n" + "z" * 100, tool_call_id="call_3", name="read_file"),
            AIMessage(content="Read FileB completed"),
            # Turn 4 (Latest query)
            HumanMessage(content="Compare FileA and FileB"),
        ]

        compacted, modified = snip.compact(messages)
        self.assertTrue(modified, "Compactor should mark messages as modified")

        # Turn 1의 list_dir (index 3)은 축약되어야 함
        turn1_tool = compacted[3]
        self.assertIsInstance(turn1_tool, ToolMessage)
        self.assertIn("[Tool result snipped: Executed 'list_dir' successfully", str(turn1_tool.content))
        self.assertEqual(turn1_tool.tool_call_id, "call_1")
        self.assertEqual(turn1_tool.name, "list_dir")

        # 가장 최근 메시지 근처의 ToolMessage는 원본 유지되어야 함
        turn3_tool = compacted[11]
        self.assertIn("function_b()", str(turn3_tool.content))

    def test_02_snip_compactor_short_tool_preserved(self):
        """80자 이하의 짧은 ToolMessage는 오래되었더라도 원본 보존"""
        snip = SnipCompactor(age_threshold=1)

        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Get status"),
            ToolMessage(content="OK (200)", tool_call_id="call_status", name="get_status"),
            AIMessage(content="Status is OK"),
            HumanMessage(content="Next step"),
        ]

        compacted, modified = snip.compact(messages)
        self.assertFalse(modified)
        self.assertEqual(compacted[2].content, "OK (200)")

    def test_03_snip_compactor_preserves_attributes(self):
        """Snip 축약 시 tool_call_id와 name 메타데이터가 손실 없이 100% 보존되는지 검증"""
        snip = SnipCompactor(age_threshold=1)

        messages = [
            HumanMessage(content="Turn 1"),
            ToolMessage(content="A" * 200, tool_call_id="call_unique_999", name="special_analyzer"),
            AIMessage(content="Turn 1 done"),
            HumanMessage(content="Turn 2"),
            AIMessage(content="Turn 2 done"),
        ]

        compacted, modified = snip.compact(messages)
        self.assertTrue(modified)
        snipped_msg = compacted[1]
        self.assertEqual(snipped_msg.tool_call_id, "call_unique_999")
        self.assertEqual(snipped_msg.name, "special_analyzer")

    # -------------------------------------------------------------------------
    # MicroCompactor Tests
    # -------------------------------------------------------------------------
    def test_04_micro_compactor_swap_large_output(self):
        """5,000자 초과 대형 출력이 디스크 스왑 파일로 저장되고 스텁으로 대체되는지 검증"""
        micro = MicroCompactor(max_chars=5000, swap_dir=self.swap_dir)

        large_payload = "<h1>Web Page Content</h1>\n" + ("Paragraph data...\n" * 500)
        self.assertGreater(len(large_payload), 5000)

        messages = [
            HumanMessage(content="Search the web for docs"),
            ToolMessage(content=large_payload, tool_call_id="call_web_1", name="web_search"),
        ]

        compacted, modified = micro.compact(messages)
        self.assertTrue(modified)

        swapped_msg = compacted[1]
        self.assertIsInstance(swapped_msg, ToolMessage)
        self.assertEqual(swapped_msg.tool_call_id, "call_web_1")
        self.assertEqual(swapped_msg.name, "web_search")

        # 스텁 내용 검증
        content = str(swapped_msg.content)
        self.assertIn("microcompacted to disk", content)
        self.assertIn(self.swap_dir, content)
        self.assertIn(f"({len(large_payload)} chars)", content)

    def test_05_micro_compactor_actionable_hint(self):
        """스텁에 read_file / grep_search를 통한 부분 조회 액션 유도형 힌트가 포함되어 있는지 검증"""
        micro = MicroCompactor(max_chars=1000, swap_dir=self.swap_dir)

        payload = "LOG ENTRY: Server started\n" + ("DEBUG: processing request\n" * 100)
        messages = [
            ToolMessage(content=payload, tool_call_id="call_log", name="read_logs")
        ]

        compacted, _ = micro.compact(messages)
        content = str(compacted[0].content)

        self.assertIn("Actionable Hint", content)
        self.assertIn("grep_search", content)
        self.assertIn("read_file", content)

    def test_06_micro_compactor_small_output_untouched(self):
        """5,000자 이하의 일반 출력은 디스크 스왑 없이 원본 유지"""
        micro = MicroCompactor(max_chars=5000, swap_dir=self.swap_dir)

        normal_payload = "Normal response: Calculation result is 42."
        messages = [
            ToolMessage(content=normal_payload, tool_call_id="call_calc", name="calculator")
        ]

        compacted, modified = micro.compact(messages)
        self.assertFalse(modified)
        self.assertEqual(compacted[0].content, normal_payload)
        self.assertEqual(len(os.listdir(self.swap_dir)), 0)

    def test_07_micro_compactor_swap_file_integrity(self):
        """생성된 스왑 파일이 디스크에 존재하며 원본 데이터와 100% 일치하는지 검증"""
        micro = MicroCompactor(max_chars=500, swap_dir=self.swap_dir)

        original_text = "Important Security Audit:\n" + ("- Found vulnerability CVE-2026-XXXX\n" * 50)
        messages = [
            ToolMessage(content=original_text, tool_call_id="call_audit", name="security_audit")
        ]

        compacted, _ = micro.compact(messages)

        # swap 파일 경로 추출
        import re
        match = re.search(r"to disk: ([^\n\]]+)", str(compacted[0].content))
        self.assertIsNotNone(match, "Swap file path must be present in stub")
        swap_path = match.group(1).strip()

        self.assertTrue(os.path.exists(swap_path), "Swap file must exist on disk")
        with open(swap_path, "r", encoding="utf-8") as f:
            disk_content = f.read()

        self.assertEqual(disk_content, original_text, "Disk content must match original text byte-for-byte")

    def test_08_micro_compactor_multi_swaps_unique(self):
        """복수 개의 대형 출력이 발생했을 때 각각 고유한 스왑 파일로 분리 생성되는지 검증"""
        micro = MicroCompactor(max_chars=500, swap_dir=self.swap_dir)

        payload_1 = "Payload 1: " + ("AAA " * 200)
        payload_2 = "Payload 2: " + ("BBB " * 200)

        messages = [
            ToolMessage(content=payload_1, tool_call_id="call_1", name="tool_1"),
            ToolMessage(content=payload_2, tool_call_id="call_2", name="tool_2"),
        ]

        compacted, modified = micro.compact(messages)
        self.assertTrue(modified)

        swap_files = os.listdir(self.swap_dir)
        self.assertEqual(len(swap_files), 2, "Should create exactly 2 distinct swap files")


if __name__ == "__main__":
    unittest.main()
