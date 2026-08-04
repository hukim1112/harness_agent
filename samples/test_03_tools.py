"""
===============================================================================
[CLI Test] 03. Tools & MCP CLI Test Script
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/tools/
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/model_tools.py
- Architecture Notes: h:/내 드라이브/work_memory/contexts/강의/handson/10_하네스_프로덕션_에이전트/references/ref_03_tools/architecture_notes.md
===============================================================================
"""

import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from harness.tools.progressive_skills import benchmark_tool_overload_penalty
from harness.tools.aci_schema_builder import build_strict_aci_tool, ProductionFileEditSchema


def main():
    print("===============================================================================")
    print("🚀 [CLI Test] Harness 03: Progressive Tools & ACI Schema Test")
    print("===============================================================================\n")

    # Test 1: 50-Tool Penalty
    print("1. Testing 50-Tool Overload Penalty...")
    pen_res = benchmark_tool_overload_penalty()
    print(f"   Penalty Slowdown Ratio: {pen_res['penalty_ratio']}x\n")

    # Test 2: Strict ACI Tool Schema
    print("2. Testing Claude Code Style Strict ACI Schema...")
    tool_aci = build_strict_aci_tool()
    print(f"   Tool Name: {tool_aci.name}")
    print(f"   Schema Name: {ProductionFileEditSchema.__name__}\n")

    print("✅ All Harness 03 CLI Tests Passed Successfully!")


if __name__ == "__main__":
    main()
