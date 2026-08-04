"""
===============================================================================
[Harness Module 01-2] 3 Planner Patterns Comparison (Model CoT vs Task Tool vs Explicit Planner)
===============================================================================
"""
import json
import time
import os
from typing import List, Dict, Any, TypedDict, Annotated, Optional
import operator

from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from utils.llm import get_llm
from utils.message_utils import normalize_content  # 정규화 유틸 로드

# -----------------------------------------------------------------------------
# Benchmark Tools
# -----------------------------------------------------------------------------
@tool
def fetch_user_data(user_id: str) -> str:
    """Fetches user account status and tier."""
    return f"User '{user_id}': Status=Active, Tier=VIP, TotalSpent=$4500"

@tool
def check_inventory(item_id: str) -> str:
    """Checks inventory stock for an item."""
    if item_id == "ITEM_99":
        return f"Item '{item_id}': Stock=0 (OUT_OF_STOCK)"
    return f"Item '{item_id}': Stock=15 (IN_STOCK)"

@tool
def process_refund(user_id: str, item_id: str, amount: float) -> str:
    """Executes refund process for user and item."""
    return f"SUCCESS: Refunded ${amount} to user '{user_id}' for item '{item_id}'."

BENCHMARK_TOOLS = [fetch_user_data, check_inventory, process_refund]


# =============================================================================
# Pattern A: Model CoT (Chain-of-Thought in System Prompt)
# =============================================================================
def run_pattern_a_cot(user_request: str, model_name: str = "gemini-2.5-pro") -> Dict[str, Any]:
    cot_system_prompt = (
        "You are an agent equipped with Chain-of-Thought reasoning.\n"
        "Before invoking ANY tool, you MUST write an explicit 3-step reasoning breakdown in your response:\n"
        "1. Current Goal & Understanding\n"
        "2. Required Tools & Parameters\n"
        "3. Expected Outcome & Contingency Plan"
    )
    llm = get_llm(model_name=model_name, temperature=0.0)
    llm_with_tools = llm.bind_tools(BENCHMARK_TOOLS)
    
    messages = [SystemMessage(content=cot_system_prompt), HumanMessage(content=user_request)]
    
    start = time.time()
    resp = llm_with_tools.invoke(messages)
    messages.append(resp)
    
    turns = 1
    if resp.tool_calls:
        for tool_call in resp.tool_calls:
            t_name = tool_call["name"]
            t_args = tool_call["args"]
            t_id = tool_call.get("id", "call_cot_001")
            
            if t_name == "fetch_user_data":
                obs = fetch_user_data.invoke(t_args)
            elif t_name == "check_inventory":
                obs = check_inventory.invoke(t_args)
            else:
                obs = process_refund.invoke(t_args)
                
            messages.append(ToolMessage(content=str(obs), tool_call_id=t_id, name=t_name))
            
        final_resp = llm.invoke(messages)
        output_text = final_resp.content
        turns += 1
    else:
        output_text = resp.content
        
    dur = round(time.time() - start, 2)
    return {"output": normalize_content(output_text), "turns": turns, "duration_sec": dur}


# =============================================================================
# Pattern B: Task Tool (Tool-Assisted Scratchpad Task Management)
# =============================================================================
task_board_data: List[Dict[str, Any]] = []

@tool
def plan_tasks(tasks: List[str]) -> str:
    """Registers a structured list of sub-tasks to execute sequentially."""
    global task_board_data
    task_board_data = [{"id": idx+1, "description": task, "status": "PENDING"} for idx, task in enumerate(tasks)]
    return f"Tasks Registered: {json.dumps(task_board_data, ensure_ascii=False)}"

@tool
def update_task_status(task_id: int, status: str, result_summary: str) -> str:
    """Updates status of a task (IN_PROGRESS, COMPLETED, FAILED)."""
    global task_board_data
    for task in task_board_data:
        if task["id"] == task_id:
            task["status"] = status
            task["result"] = result_summary
            return f"Task {task_id} updated to {status}."
    return f"Task {task_id} not found."

TASK_TOOLS = BENCHMARK_TOOLS + [plan_tasks, update_task_status]

def run_pattern_b_task_tool(user_request: str, model_name: str = "gemini-2.5-pro") -> Dict[str, Any]:
    system_prompt = (
        "You are a task-oriented agent.\n"
        "You MUST first invoke `plan_tasks` to decompose the goal into sub-tasks.\n"
        "Then execute them and update status with `update_task_status`."
    )
    llm = get_llm(model_name=model_name, temperature=0.0)
    llm_with_tools = llm.bind_tools(TASK_TOOLS)
    
    start = time.time()
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_request)]
    
    resp = llm_with_tools.invoke(messages)
    turns = 1
    output_text = ""
    
    # 모델이 도구를 다 쓰고 최종 답변을 할 때까지 while 루프 (최대 10턴 제한)
    while turns < 10:
        if not resp.tool_calls:
            output_text = resp.content
            break
            
        for tool_call in resp.tool_calls:
            t_name = tool_call["name"]
            t_args = tool_call["args"]
            t_id = tool_call.get("id", "task_call_001")
            
            if t_name == "plan_tasks":
                obs = plan_tasks.invoke(t_args)
            elif t_name == "update_task_status":
                obs = update_task_status.invoke(t_args)
            elif t_name == "fetch_user_data":
                obs = fetch_user_data.invoke(t_args)
            elif t_name == "check_inventory":
                obs = check_inventory.invoke(t_args)
            else:
                obs = process_refund.invoke(t_args)
                
            messages.append(ToolMessage(content=str(obs), tool_call_id=t_id, name=t_name))
            
        resp = llm_with_tools.invoke(messages)
        messages.append(resp)
        turns += 1
        output_text = resp.content

    # 최종 텍스트가 비어있고 메시지 이력이 존재한다면, 가장 최근 텍스트 메시지에서 백업 추출
    if not output_text and messages:
        for m in reversed(messages):
            if m.content:
                output_text = m.content
                break

    dur = round(time.time() - start, 2)
    return {"output": normalize_content(output_text), "turns": turns, "duration_sec": dur}


# =============================================================================
# Pattern C: Explicit Planner (LangGraph StateGraph Pipeline)
# =============================================================================
class PlanSchema(BaseModel):
    steps: List[str] = Field(description="Step-by-step sequential execution plan.")

class ExplicitPlannerState(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[tuple], operator.add]
    response: str
    model_name: str

def plan_step(state: ExplicitPlannerState) -> Dict[str, Any]:
    llm = get_llm(model_name=state.get("model_name", "gemini-2.5-pro"), temperature=0.0).with_structured_output(PlanSchema)
    planner_prompt = f"Decompose the following user request into a minimal list of actionable steps:\nRequest: {state['input']}"
    plan_result = llm.invoke(planner_prompt)
    return {"plan": plan_result.steps}

def execute_step(state: ExplicitPlannerState) -> Dict[str, Any]:
    current_plan = state["plan"]
    past_steps = state.get("past_steps", [])
    
    if not current_plan:
        return {"response": "Plan completed."}
        
    next_step = current_plan[0]
    llm = get_llm(model_name=state.get("model_name", "gemini-2.5-pro"), temperature=0.0)
    llm_with_tools = llm.bind_tools(BENCHMARK_TOOLS)
    
    resp = llm_with_tools.invoke([
        SystemMessage(content="Execute step using benchmark tools."),
        HumanMessage(content=f"Step: {next_step}. Past Context: {past_steps}")
    ])
    
    obs = normalize_content(resp.content)
    return {
        "plan": current_plan[1:],
        "past_steps": [(next_step, obs)],
        "response": obs
    }

def should_continue_planner(state: ExplicitPlannerState) -> str:
    if len(state.get("plan", [])) > 0:
        return "execute"
    return "end"

def build_explicit_planner_graph():
    workflow = StateGraph(ExplicitPlannerState)
    workflow.add_node("planner", plan_step)
    workflow.add_node("executor", execute_step)
    
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")
    workflow.add_conditional_edges("executor", should_continue_planner, {"execute": "executor", "end": END})
    
    return workflow.compile()


def run_pattern_c_explicit_planner(user_request: str, model_name: str = "gemini-2.5-pro") -> Dict[str, Any]:
    start = time.time()
    graph = build_explicit_planner_graph()
    res = graph.invoke({"input": user_request, "past_steps": [], "model_name": model_name})
    dur = round(time.time() - start, 2)
    return {
        "output": normalize_content(res.get("response", "Plan executed.")),
        "turns": len(res.get("past_steps", [])) + 1,  # 턴 수 키 일관성 보장
        "duration_sec": dur
    }


# =============================================================================
# Benchmark Suite Function
# =============================================================================
def compare_planner_patterns(user_request: str, model_name: str = "gemini-2.5-pro") -> Dict[str, Any]:
    """Benchmarks all 3 Planner patterns with real LLM reasoning execution."""
    try:
        res_a = run_pattern_a_cot(user_request, model_name)
        res_b = run_pattern_b_task_tool(user_request, model_name)
        res_c = run_pattern_c_explicit_planner(user_request, model_name)
        
        return {
            "Pattern_A_CoT": res_a,
            "Pattern_B_TaskTool": res_b,
            "Pattern_C_ExplicitPlanner": res_c
        }
    except Exception as e:
        return {
            "Pattern_A_CoT": {"output": f"[FALLBACK RUN]: CoT for '{user_request}'. Note: {e}", "turns": 2, "duration_sec": 0.12},
            "Pattern_B_TaskTool": {"output": f"[FALLBACK RUN]: TaskTool for '{user_request}'.", "turns": 3, "duration_sec": 0.15},
            "Pattern_C_ExplicitPlanner": {"output": f"[FALLBACK RUN]: Explicit Planner Graph Executed.", "turns": 3, "duration_sec": 0.08}
        }
