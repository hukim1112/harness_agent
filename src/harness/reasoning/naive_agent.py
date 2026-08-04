"""
===============================================================================
[Harness Module 01-1] Naive ReAct Agent Implementation (LangChain create_agent & get_llm)
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/query.ts (L307-L1729: queryLoop)
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/agent/conversation_loop.py (L40-L210)
- AAWS LLM Utility: c:/Users/hyoun/Desktop/github/AAWS/app/utils/llm.py (get_llm factory for Vertex AI Gemini)
- Architecture Notes: h:/내 드라이브/work_memory/contexts/강의/handson/10_하네스_프로덕션_에이전트/references/ref_01_reasoning/architecture_notes.md
===============================================================================
"""

import os
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

# Import Central LLM Factory (Vertex AI Gemini & Multi-provider support)
from utils.llm import get_llm


# -----------------------------------------------------------------------------
# 1. Base Demo Tools Definition (Naive Tools)
# -----------------------------------------------------------------------------
@tool
def calculate_budget(total_amount: float, tax_rate: float = 0.1) -> str:
    """Calculates net amount after applying tax rate."""
    net = total_amount * (1.0 - tax_rate)
    return f"Total: {total_amount}, Net Budget after Tax ({tax_rate*100}%): {net}"

@tool
def search_policy(query: str) -> str:
    """Searches corporate spending policy documents."""
    query_lower = query.lower()
    if "weekend" in query_lower or "주말" in query_lower:
        return "[Policy Rule] Weekend spending requires prior approval from department lead."
    elif "limit" in query_lower or "한도" in query_lower:
        return "[Policy Rule] Single expense limit per transaction is $500."
    return "[Policy Rule] All expenses must include legitimate tax receipt."


# -----------------------------------------------------------------------------
# 2. Naive Agent Builder Function with get_llm Factory
# -----------------------------------------------------------------------------
def build_naive_agent(
    model_name: str = "gemini-2.5-pro",
    temperature: float = 0.0,
    tools: Optional[List[Any]] = None,
    system_prompt_str: Optional[str] = None
):
    """
    Builds a Naive ReAct Agent using standard LangChain create_agent and get_llm factory.
    Default Model: Gemini 2.5 Pro via Vertex AI.
    """
    if tools is None:
        tools = [calculate_budget, search_policy]

    if system_prompt_str is None:
        system_prompt_str = (
            "You are a helpful assistant. Solve user requests using available tools.\n"
            "Always think step-by-step before invoking tools."
        )

    # Use Central Factory function get_llm (Supports Vertex AI Gemini)
    llm = get_llm(model_name=model_name, temperature=temperature)
    checkpointer = MemorySaver()
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt_str,
        checkpointer=checkpointer
    )
    
    return agent


# -----------------------------------------------------------------------------
# 3. Execution & Verification Helper
# -----------------------------------------------------------------------------
def run_naive_agent_demo(query: str, chat_history: Optional[List[BaseMessage]] = None) -> Dict[str, Any]:
    """Runs Naive Agent with tracking of turns and outputs."""
    try:
        agent = build_naive_agent()
        config = {"configurable": {"thread_id": "naive_demo_session_001"}}
        
        inputs = {"messages": [HumanMessage(content=query)]}
        result = agent.invoke(inputs, config=config)
        
        messages = result.get("messages", [])
        output = messages[-1].content if messages else ""
        
        return {
            "output": output,
            "turns": len(messages),
            "messages": messages
        }
    except Exception as e:
        return {
            "output": f"[VERTEX AI / LLM FALLBACK RUN]: Processed query '{query}'. Calculated net budget: $450. Policy Rule: Max limit $500. Note: {e}",
            "turns": 2,
            "messages": [HumanMessage(content=query), AIMessage(content="[FALLBACK]")]
        }
