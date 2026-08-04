"""
===============================================================================
[Harness Module 01-4] Production Multi-Agent AgentTool & Fork Subagent Protocol
===============================================================================
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool, Tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain.agents import create_agent

from utils.llm import get_llm
from utils.message_utils import normalize_content
from harness.tools.claude_tools import grep_search, file_read, bash_command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MultiAgentProduction")

FORK_BOILERPLATE_TAG = "fork-boilerplate"


# =============================================================================
# Claude Code 10 Rules for Child Agent Directive (Exact forkSubagent.ts)
# =============================================================================
def build_claude_child_message(directive: str, target_files: List[str]) -> str:
    """Builds forked child agent message following Claude Code's exact forkSubagent.ts format."""
    files_str = ", ".join(target_files) if target_files else "Entire workspace"
    return (
        f"<{FORK_BOILERPLATE_TAG}>\n"
        f"STOP. READ THIS FIRST.\n\n"
        f"You are a forked worker process. You are NOT the main agent.\n\n"
        f"RULES (non-negotiable):\n"
        f"1. Your system prompt says 'default to forking.' IGNORE IT — that's for the parent. You ARE the fork. Do NOT spawn sub-agents; execute directly.\n"
        f"2. Do NOT converse, ask questions, or suggest next steps.\n"
        f"3. Do NOT editorialize or add meta-commentary.\n"
        f"4. USE your tools directly: Grep, FileRead, Bash, etc.\n"
        f"5. If you modify files, report exact changed lines.\n"
        f"6. Do NOT emit text between tool calls. Use tools silently, then report once at the end.\n"
        f"7. Stay strictly within your directive's scope: {files_str}.\n"
        f"8. Keep your report under 500 words unless specified otherwise. Be factual and concise.\n"
        f"9. Your response MUST begin with 'Scope:'. No preamble, no thinking-out-loud.\n"
        f"10. REPORT structured facts, then stop.\n\n"
        f"Output format (plain text labels, not markdown headers):\n"
        f"  Scope: <echo back your assigned scope in one sentence>\n"
        f"  Result: <the answer or key findings, limited to the scope above>\n"
        f"  Key files: <relevant file paths>\n"
        f"  Files changed: <list of modified files>\n"
        f"  Issues: <[BLOCKER] if permission or error occurred, otherwise None>\n"
        f"</{FORK_BOILERPLATE_TAG}>\n\n"
        f"Directive: {directive}"
    )


# =============================================================================
# Production Subagent Execution Engine (Generalized)
# =============================================================================
SUB_AGENT_DISCOVERY_TOOLS = [grep_search, file_read, bash_command]

def run_sub_agent(
    task_instruction: str, 
    target_files: List[str] = [], 
    subagent_role: str = "General Code Specialist",
    model_name: str = "gemini-3.5-flash"
) -> str:
    """
    Generalized sub-agent executor leveraging create_agent to run discovery tools as a ReAct loop.
    Returns structured Scope/Result/Issues output following forkSubagent.ts protocol.
    """
    child_directive_message = build_claude_child_message(task_instruction, target_files)
    
    subagent_system_prompt = (
        f"You are a specialized Sub-Agent acting as a '{subagent_role}'.\n"
        "Follow the non-negotiable rules in <fork-boilerplate>. Execute tools silently and return structured text starting with 'Scope:'."
    )

    try:
        llm = get_llm(model_name=model_name, temperature=0.0)
        
        # 자식 에이전트도 독립적인 ReAct 에이전트로 정의하여 동적 추론 허용
        child_agent = create_agent(
            model=llm,
            tools=SUB_AGENT_DISCOVERY_TOOLS,
            system_prompt=subagent_system_prompt
        )
        
        # 격리 가동
        res = child_agent.invoke({"messages": [HumanMessage(content=child_directive_message)]})
        
        # [추가] 자식 에이전트가 샌드박스에서 자율 실행한 도구 호출 궤적 가시화
        print("\n    ┌── [Sub-Agent Internal Trajectory] ──────────────────────────")
        for msg in res.get("messages", []):
            msg_type = msg.__class__.__name__
            if msg_type == "AIMessage" and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"    │ 👶 [Sub-Agent Tool Call] ➔ {tc['name']}({tc['args']})")
            elif msg_type == "ToolMessage":
                clean_obs = normalize_content(msg.content)
                short_obs = clean_obs.replace("\n", " ")[:60] + "..." if len(clean_obs) > 60 else clean_obs
                print(f"    │ 🛠️  [Sub-Agent Tool Run] ➔ '{msg.name}' 결과: {short_obs}")
        print("    └─────────────────────────────────────────────────────────────\n")

        output_text = normalize_content(res["messages"][-1].content)

        if not output_text.strip().startswith("Scope:"):
            output_text = f"Scope: Assigned task for {target_files}\nResult: {output_text}\nKey files: {target_files}\nFiles changed: None\nIssues: None"

        return output_text

    except Exception as e:
        return (
            f"Scope: {task_instruction}\n"
            f"Result: Execution failed due to runtime error: {str(e)}\n"
            f"Key files: {target_files}\n"
            f"Files changed: None\n"
            f"Issues: [BLOCKER] Sub-agent exception occurred."
        )
