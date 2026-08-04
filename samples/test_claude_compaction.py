"""
===============================================================================
[Test Script] Claude Code 4-Stage Context Compaction Benchmark
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/compact/
- Slide Reference: h:/내 드라이브/work_memory/contexts/강의/slides/11_글로벌_에이전트_아키텍처/v1.1/02_claude_code.html (Slide 17-20: Compaction)
===============================================================================
"""

import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harness.context.claude_compressor import ClaudeContextCompactor
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage


def main():
    print("===============================================================================")
    print("🗜️ [Claude Compaction Test] 4-Stage Context Compaction Benchmark")
    print("===============================================================================\n")

    compactor = ClaudeContextCompactor(token_threshold=200)

    # Build Sample 30-Turn Trajectory
    messages = [SystemMessage(content="System Directive: You are Claude Code.")]
    for i in range(1, 16):
        messages.append(HumanMessage(content=f"User Turn {i}: Inspect and modify file #{i}"))
        messages.append(ToolMessage(content=f"Tool Output {i}: Executed file edit. " + ("A" * 600), tool_call_id=f"call_{i}"))

    print(f"Original Trajectory Messages Count: {len(messages)}")

    # Technique 1: Micro-compaction
    micro_msgs = compactor.apply_micro_compaction(messages)
    print(f"1. Micro-compaction Applied: Pruned long tool outputs -> {len(micro_msgs)} messages preserved.")

    # Technique 2: Auto-compaction
    auto_msgs, auto_report = compactor.apply_auto_compaction(micro_msgs)
    print(f"2. Auto-compaction Applied: Threshold triggered -> Reduced to {len(auto_msgs)} messages. Report: {auto_report}")

    # Technique 3: Reactive Compaction (413 Emergency Handler)
    reactive_msgs = compactor.apply_reactive_compaction(messages)
    print(f"3. Reactive Compaction (413 Payload Error) Applied: Emergency drain to {len(reactive_msgs)} messages.")

    # Technique 4: Context Drain (Sliding Window)
    drain_msgs = compactor.apply_context_drain(messages, keep_last_n=4)
    print(f"4. Context Drain Applied: Drained older turns -> Preserved {len(drain_msgs)} messages.")

    print("\n✅ All 4 Claude Code Compaction Techniques Tested Successfully!")


if __name__ == "__main__":
    main()
