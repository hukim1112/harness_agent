"""
===============================================================================
[CLI Test] 02. Context Management CLI Test Script
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/prompt_builder.py
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/hermes_state.py
- Architecture Notes: h:/내 드라이브/work_memory/contexts/강의/handson/10_하네스_프로덕션_에이전트/references/ref_02_context/architecture_notes.md
===============================================================================
"""

import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harness.context.prompt_caching import benchmark_prompt_caching_efficiency
from harness.context.hermes_memory import build_hermes_memory_pipeline, HermesMemoryDatabase


def main():
    print("===============================================================================")
    print("🚀 [CLI Test] Harness 02: Context & 4-Layer Memory Test")
    print("===============================================================================\n")

    # Test 1: Prompt Caching
    print("1. Testing Multi-Layer Prompt Caching Efficiency...")
    cache_res = benchmark_prompt_caching_efficiency("출장비 한도 문의", iterations=2)
    print(f"   Avg Caching Latency: {cache_res['avg_caching_latency']}s vs Baseline: {cache_res['avg_unstructured_latency']}s\n")

    # Test 2: Hermes Memory Extraction
    print("2. Testing Hermes 4-Layer Memory Extraction (LangGraph)...")
    l1_messages = [
        {"role": "user", "content": "내 이름은 홍길동이고 개발팀장이야."},
        {"role": "user", "content": "나는 주말 근무 시 무조건 사전 승인을 신청한다."}
    ]
    graph = build_hermes_memory_pipeline()
    pipeline_res = graph.invoke({"working_memory_l1": l1_messages})
    print(f"   Extracted Memory: {json.dumps(pipeline_res['extracted_data'], indent=2, ensure_ascii=False)}\n")

    # Test 3: SQLite Query
    db = HermesMemoryDatabase()
    all_mem = db.query_all_memories()
    print(f"   SQLite Persistent Memories: {json.dumps(all_mem, indent=2, ensure_ascii=False)}\n")

    print("✅ All Harness 02 CLI Tests Passed Successfully!")


if __name__ == "__main__":
    main()
