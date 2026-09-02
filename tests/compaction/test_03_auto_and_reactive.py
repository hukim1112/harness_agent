"""
=============================================================================
Test 03: AutoCompactor & ReactiveCompactor 단위 테스트
=============================================================================
1. AutoCompactor:
   - 토큰 임계치 이하일 때 No-Op (메시지 보존)
   - 토큰 초과 시 LLM을 통한 4-Section 구조화 요약 생성
   - 시스템 프롬프트(L1~L5) 및 최신 HumanMessage 보존
   - LLM 예외 발생 시 Fallback 요약 안전 동작
2. ReactiveCompactor:
   - 413 API 에러 포획 및 Silent 20% Tail Slicing
   - 슬라이싱 후 복원 안내 SystemMessage 주입
   - 대화 메시지가 극단적으로 적을 때의 안전 자르기 처리
=============================================================================
"""

import unittest
from unittest.mock import MagicMock
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from app.middleware.compaction.compactor import AutoCompactor, ReactiveCompactor


class MockLLM:
    """Mock LLM for AutoCompactor token counting and summarization"""
    def __init__(self, summary_text: str = "1. Goal: Build API\n2. Key Decisions: Use FastAPI\n3. Code Delta: Created auth.py\n4. Next: Add JWT tests"):
        self.summary_text = summary_text
        self.call_count = 0

    def get_num_tokens_from_messages(self, messages: list) -> int:
        # Approximate 1 token per 4 chars for realistic mocking
        return sum(len(str(m.content)) for m in messages) // 4

    def invoke(self, messages: list):
        self.call_count += 1
        return AIMessage(content=self.summary_text)


class TestAutoAndReactiveCompactor(unittest.TestCase):
    # -------------------------------------------------------------------------
    # AutoCompactor Tests
    # -------------------------------------------------------------------------
    def test_01_auto_compactor_below_threshold_no_op(self):
        """토큰 수가 임계치(8,000) 이하일 때는 요약하지 않고 원본 유지"""
        mock_llm = MockLLM()
        auto = AutoCompactor(llm=mock_llm, threshold_tokens=8000)

        messages = [
            SystemMessage(content="System L1-L5"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]

        compacted, modified = auto.compact_if_needed(messages)
        self.assertFalse(modified)
        self.assertEqual(len(compacted), 3)
        self.assertEqual(mock_llm.call_count, 0)

    def test_02_auto_compactor_above_threshold_summary(self):
        """토큰 임계치 초과 시 이전 대화 전체가 4-Section 요약으로 압축되는지 검증"""
        mock_llm = MockLLM()
        # threshold를 작게 설정 (100 토큰)
        auto = AutoCompactor(llm=mock_llm, threshold_tokens=100)

        messages = [
            SystemMessage(content="[L1-L5] System Identity and Dynamic Docs"),
            HumanMessage(content="Long message 1: " + "A" * 300),
            AIMessage(content="Long response 1: " + "B" * 300),
            HumanMessage(content="Long message 2: " + "C" * 300),
            AIMessage(content="Long response 2: " + "D" * 300),
            # Latest turn
            HumanMessage(content="What should we do next?"),
        ]

        compacted, modified = auto.compact_if_needed(messages)
        self.assertTrue(modified)
        self.assertEqual(mock_llm.call_count, 1)

        # Structure: SystemMessage + Summary SystemMessage + Latest HumanMessage
        self.assertEqual(len(compacted), 3)
        self.assertEqual(compacted[0].content, "[L1-L5] System Identity and Dynamic Docs")

        summary_msg = compacted[1]
        self.assertIsInstance(summary_msg, SystemMessage)
        self.assertIn("Previous Conversation Summary:", summary_msg.content)
        self.assertIn("1. Goal: Build API", summary_msg.content)
        self.assertIn("2. Key Decisions: Use FastAPI", summary_msg.content)

        # 최신 질문이 온전히 유지되어야 함
        last_msg = compacted[2]
        self.assertIsInstance(last_msg, HumanMessage)
        self.assertEqual(last_msg.content, "What should we do next?")

    def test_03_auto_compactor_fallback_on_llm_error(self):
        """LLM 호출 중 예외 발생 시 에러가 중단되지 않고 Fallback 요약이 생성되는지 검증"""
        faulty_llm = MagicMock()
        faulty_llm.get_num_tokens_from_messages.return_value = 10000
        faulty_llm.invoke.side_effect = RuntimeError("API Rate Limit or Connection Error")

        auto = AutoCompactor(llm=faulty_llm, threshold_tokens=1000)

        messages = [
            SystemMessage(content="System rules"),
            HumanMessage(content="Question 1"),
            AIMessage(content="Answer 1"),
            HumanMessage(content="Latest Question"),
        ]

        compacted, modified = auto.compact_if_needed(messages)
        self.assertTrue(modified)

        summary_msg = compacted[1]
        self.assertIn("Error generating summary: API Rate Limit or Connection Error", summary_msg.content)
        self.assertIn("Raw message count: 2", summary_msg.content)

    # -------------------------------------------------------------------------
    # ReactiveCompactor Tests
    # -------------------------------------------------------------------------
    def test_04_reactive_compactor_handles_413_slicing(self):
        """413 에러 발생 시 오래된 대화 메시지의 20%를 잘라내고 재구성하는지 검증"""
        reactive = ReactiveCompactor(slice_ratio=0.20)

        messages = [SystemMessage(content="System Core")]
        # 10 dialogue turns (total 10 messages)
        for i in range(10):
            messages.append(HumanMessage(content=f"Message {i}"))

        # handle_overflow 실행
        recovered = reactive.handle_overflow(messages)

        # 10개의 dialogue 중 20% = 2개 슬라이싱 (Message 0, Message 1)
        # Structure: SystemMessage + Reactive Summary SystemMessage + 8 dialogue messages = 10 messages
        self.assertEqual(len(recovered), 10)
        self.assertEqual(recovered[0].content, "System Core")

        reactive_summary = recovered[1]
        self.assertIsInstance(reactive_summary, SystemMessage)
        self.assertIn("[Reactive Compact (Silent Withholding)]", reactive_summary.content)
        self.assertIn("Emergency sliced oldest 2 dialogue messages", reactive_summary.content)

        # Message 2부터 남아있어야 함
        self.assertEqual(recovered[2].content, "Message 2")
        self.assertEqual(recovered[-1].content, "Message 9")

    def test_05_reactive_compactor_short_dialogue_fallback(self):
        """대화 메시지가 2개 이하로 극단적으로 짧은 상태에서 오버플로우 발생 시 페이로드 직접 자르기"""
        reactive = ReactiveCompactor(slice_ratio=0.20)

        huge_payload = "GIANT INPUT: " + "Z" * 10000
        messages = [
            SystemMessage(content="System Core"),
            HumanMessage(content=huge_payload),
        ]

        recovered = reactive.handle_overflow(messages)
        self.assertEqual(len(recovered), 2)
        truncated_msg = recovered[1]
        self.assertIn("... [Reactive Compact: Truncated 413 payload]", truncated_msg.content)
        self.assertLess(len(truncated_msg.content), 2000)


if __name__ == "__main__":
    unittest.main()
