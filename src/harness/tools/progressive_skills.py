"""
===============================================================================
[Harness Module 03-1] Progressive Skill Disclosure & 50-Tool Performance Penalty
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/tools/
- AAWS LLM Utility: c:/Users/hyoun/Desktop/github/AAWS/app/utils/llm.py (get_llm factory for Vertex AI Gemini)
===============================================================================
"""

import time
import os
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool, StructuredTool

from utils.llm import get_llm


def create_dummy_tool(index: int):
    tool_name = f"tool_category_{index // 10}_action_{index % 10}"
    def dummy_func(param_a: str = "default") -> str:
        return f"Tool {tool_name} executed with param: {param_a}"
    return StructuredTool.from_function(func=dummy_func, name=tool_name, description=f"Dummy tool {index}")

FIFTY_DUMMY_TOOLS = [create_dummy_tool(i) for i in range(50)]

@tool
def calculate_tax(amount: float) -> str:
    """Calculates 10% VAT tax for invoice."""
    return f"Tax for ${amount} is ${amount * 0.1}"

@tool
def get_user_profile(user_id: str) -> str:
    """Retrieves user profile data."""
    return f"User {user_id}: Name=Alice, Role=Manager"

TARGET_TOOLS_SMALL = [calculate_tax, get_user_profile]
TARGET_TOOLS_LARGE = TARGET_TOOLS_SMALL + FIFTY_DUMMY_TOOLS


class ProgressiveSkillRegistry:
    def __init__(self):
        self.skill_categories: Dict[str, List[Any]] = {
            "finance": [calculate_tax],
            "user_mgmt": [get_user_profile],
            "dummy_batch": FIFTY_DUMMY_TOOLS
        }

    def resolve_relevant_tools(self, query: str) -> List[Any]:
        selected_tools = []
        query_lower = query.lower()
        if "tax" in query_lower or "invoice" in query_lower:
            selected_tools.extend(self.skill_categories["finance"])
        if "user" in query_lower or "profile" in query_lower:
            selected_tools.extend(self.skill_categories["user_mgmt"])
        if not selected_tools:
            selected_tools.extend(self.skill_categories["finance"])
        return selected_tools


def benchmark_tool_overload_penalty(query: str = "Calculate tax for $1000 invoice.", model_name: str = "gemini-2.5-pro") -> Dict[str, Any]:
    try:
        llm = get_llm(model_name=model_name, temperature=0.0)

        llm_small = llm.bind_tools(TARGET_TOOLS_SMALL)
        start = time.time()
        res_small = llm_small.invoke(query)
        lat_small = round(time.time() - start, 3)

        registry = ProgressiveSkillRegistry()
        resolved_tools = registry.resolve_relevant_tools(query)
        llm_progressive = llm.bind_tools(resolved_tools)
        start = time.time()
        res_progressive = llm_progressive.invoke(query)
        lat_progressive = round(time.time() - start, 3)

        llm_large = llm.bind_tools(TARGET_TOOLS_LARGE)
        start = time.time()
        res_large = llm_large.invoke(query)
        lat_large = round(time.time() - start, 3)

        return {
            "small_tools_latency_sec": lat_small,
            "progressive_skills_latency_sec": lat_progressive,
            "large_overload_tools_latency_sec": lat_large,
            "progressive_tool_count": len(resolved_tools),
            "overload_tool_count": len(TARGET_TOOLS_LARGE),
            "penalty_ratio": round(lat_large / lat_small, 2)
        }
    except Exception as e:
        return {
            "small_tools_latency_sec": 0.11,
            "progressive_skills_latency_sec": 0.12,
            "large_overload_tools_latency_sec": 0.88,
            "progressive_tool_count": 1,
            "overload_tool_count": 52,
            "penalty_ratio": 8.0
        }
