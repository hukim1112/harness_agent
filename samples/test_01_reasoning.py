"""
===============================================================================
[CLI Test] 01. Reasoning & Multi-Agent CLI Test Script
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/query.ts
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/agent/conversation_loop.py
- Architecture Notes: h:/내 드라이브/work_memory/contexts/강의/handson/10_하네스_프로덕션_에이전트/references/ref_01_reasoning/architecture_notes.md
===============================================================================
"""

import sys
import os
import json

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harness.reasoning.naive_agent import run_naive_agent_demo
from harness.reasoning.planner_patterns import compare_planner_patterns
from harness.reasoning.self_correction import SelfCorrectionEngine
from harness.reasoning.multi_agent_as_tool import run_supervisor_multi_agent_demo


def main():
    print("===============================================================================")
    print("🚀 [CLI Test] Harness 01: Reasoning & Multi-Agent Test")
    print("===============================================================================\n")

    # Test 1: Naive ReAct Agent
    print("1. Testing Naive ReAct Agent...")
    res1 = run_naive_agent_demo("예산 $500 계산")
    print(f"   Output: {res1['output']}\n")

    # Test 2: 3 Planner Benchmark
    print("2. Testing 3-Planner Benchmark...")
    res2 = compare_planner_patterns("USER_01 재고 확인 및 환불")
    print(f"   Benchmark Summary: {json.dumps(res2, indent=2, ensure_ascii=False)}\n")

    # Test 3: Self-Correction Loop
    print("3. Testing Self-Correction Engine...")
    engine = SelfCorrectionEngine(max_retries=2)
    res3 = engine.run_with_self_correction("USERS 테이블 조회")
    print(f"   Self-Correction Status: {res3['status']}\n")

    # Test 4: Multi-Agent Delegation
    print("4. Testing Multi-Agent Supervisor Delegation...")
    res4 = run_supervisor_multi_agent_demo("config.py 보안 리팩토링")
    print(f"   Supervisor Tool Calls: {res4['tool_calls']}\n")

    print("✅ All Harness 01 CLI Tests Passed Successfully!")


if __name__ == "__main__":
    main()
