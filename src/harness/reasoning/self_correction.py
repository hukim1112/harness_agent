"""
===============================================================================
[Harness Module 01-3] 17-Transition State Engine & Auto Recovery Self-Correction Loop
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/superview.sh-claude-code/src/query.ts (queryLoop transitions)
- Slide Reference: h:/내 드라이브/work_memory/contexts/강의/slides/11_글로벌_에이전트_아키텍처/v1.1/02_claude_code.html (Slide 16-17: 17 Transitions)
- Architecture Notes: h:/내 드라이브/work_memory/contexts/강의/handson/10_하네스_프로덕션_에이전트/references/ref_01_reasoning/architecture_notes.md
===============================================================================
"""

import logging
import os
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from utils.llm import get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("17TransitionEngine")


class ExitTransition(Enum):
    COMPLETED = "completed"
    BLOCKING_LIMIT = "blocking_limit"
    PROMPT_TOO_LONG = "prompt_too_long"
    MAX_TURNS = "max_turns"
    ABORTED_STREAMING = "aborted_streaming"
    ABORTED_TOOLS = "aborted_tools"
    MODEL_ERROR = "model_error"
    STOP_HOOK_PREVENTED = "stop_hook_prevented"
    HOOK_STOPPED = "hook_stopped"
    IMAGE_ERROR = "image_error"


class ContinueTransition(Enum):
    NEXT_TURN = "next_turn"
    REACTIVE_COMPACT_RETRY = "reactive_compact_retry"
    COLLAPSE_DRAIN_RETRY = "collapse_drain_retry"
    MAX_OUTPUT_TOKENS_ESCALATE = "max_output_tokens_escalate"
    MAX_OUTPUT_TOKENS_RECOVERY = "max_output_tokens_recovery"
    STOP_HOOK_BLOCKING = "stop_hook_blocking"
    TOKEN_BUDGET_CONTINUATION = "token_budget_continuation"


@tool
def execute_database_query(query_sql: str) -> str:
    """Executes SQL query against database with strict policies."""
    if "SELECT *" in query_sql.upper():
        raise ValueError("SECURITY_POLICY_VIOLATION: Wildcard 'SELECT *' is prohibited. Specify explicit column names.")
    elif "USERS" in query_sql.upper() and "LIMIT" not in query_sql.upper():
        raise ValueError("PERFORMANCE_POLICY_VIOLATION: Queries on 'USERS' table must include a LIMIT clause.")
    elif "413_TRIGGER" in query_sql.upper():
        raise RuntimeError("413_PROMPT_TOO_LONG: Payload size 413 request entity too large.")
    elif "OUTPUT_OVERFLOW" in query_sql.upper():
        raise RuntimeError("MAX_OUTPUT_TOKENS_REACHED: Token limit reached.")
    return f"Query Success: Returned 5 rows for query '{query_sql}'"


class AutoRecovery17TransitionEngine:
    def __init__(self, model_name: str = "gemini-2.5-pro", max_turns: int = 10, max_output_token_limit: int = 8192):
        self.model_name = model_name
        self.max_turns = max_turns
        self.output_token_limit = max_output_token_limit
        self.resume_recovery_count = 0
        self.tools_map = {"execute_database_query": execute_database_query}

    def run_engine(self, user_goal: str) -> Dict[str, Any]:
        messages = [
            SystemMessage(content=(
                "You are an enterprise database agent.\n"
                "Execute SQL queries using `execute_database_query`.\n"
                "If an error occurs, analyze the error feedback, correct your query, and resume."
            )),
            HumanMessage(content=user_goal)
        ]
        
        turn_count = 0
        transition_history = []

        while True:
            turn_count += 1
            if turn_count > self.max_turns:
                transition_history.append((ExitTransition.MAX_TURNS.value, f"Turn count {turn_count} > max_turns {self.max_turns}"))
                return {"exit_reason": ExitTransition.MAX_TURNS.value, "status": "FAILED", "turns": turn_count, "history": transition_history}

            try:
                llm = get_llm(model_name=self.model_name, temperature=0.0)
                llm_with_tools = llm.bind_tools(list(self.tools_map.values()))
                
                resp = llm_with_tools.invoke(messages)
                messages.append(resp)

                if not resp.tool_calls:
                    transition_history.append((ExitTransition.COMPLETED.value, "Normal completion without tool calls"))
                    return {"exit_reason": ExitTransition.COMPLETED.value, "status": "SUCCESS", "final_output": resp.content, "turns": turn_count, "history": transition_history}

                tool_call = resp.tool_calls[0]
                t_name = tool_call["name"]
                t_args = tool_call["args"]
                t_id = tool_call.get("id", f"call_{turn_count}")

                try:
                    target_tool = self.tools_map[t_name]
                    result = target_tool.invoke(t_args)
                    messages.append(ToolMessage(content=str(result), tool_call_id=t_id))
                    transition_history.append((ContinueTransition.NEXT_TURN.value, f"Executed tool '{t_name}' successfully."))
                    
                    final_resp = llm.invoke(messages)
                    transition_history.append((ExitTransition.COMPLETED.value, "Completed after tool execution."))
                    return {"exit_reason": ExitTransition.COMPLETED.value, "status": "SUCCESS", "final_output": final_resp.content, "turns": turn_count, "history": transition_history}

                except Exception as err:
                    error_str = str(err)
                    if "413" in error_str or "PROMPT_TOO_LONG" in error_str:
                        transition_history.append((ContinueTransition.REACTIVE_COMPACT_RETRY.value, "Caught 413 Error -> Reactive Compaction Activated"))
                        messages = [messages[0], messages[1], HumanMessage(content="[REACTIVE_COMPACTED_TRAJECTORY]: Pruned older turns.")]
                        continue
                    else:
                        transition_history.append((ContinueTransition.STOP_HOOK_BLOCKING.value, f"Injected Error Feedback: {error_str}"))
                        correction_prompt = f"[ERROR_FEEDBACK - Auto Recovery Required]\nTool '{t_name}' failed: {error_str}\nFix parameters and retry."
                        messages.append(HumanMessage(content=correction_prompt))

            except Exception as outer_err:
                transition_history.append((ExitTransition.MODEL_ERROR.value, str(outer_err)))
                return {"exit_reason": ExitTransition.MODEL_ERROR.value, "status": "FAILED_WITH_AUTO_RECOVERY_LOG", "turns": turn_count, "history": transition_history}


class SelfCorrectionEngine:
    def __init__(self, model_name: str = "gemini-2.5-pro", max_retries: int = 3):
        self.engine = AutoRecovery17TransitionEngine(model_name=model_name, max_turns=max_retries)

    def run_with_self_correction(self, user_goal: str) -> Dict[str, Any]:
        res = self.engine.run_engine(user_goal)
        return {
            "status": "SUCCESS_AFTER_SELF_CORRECTION" if res.get("status") == "SUCCESS" else "FAILED",
            "final_output": res.get("final_output", "Processed."),
            "attempts": res.get("turns", 1),
            "history": res.get("history", [])
        }
