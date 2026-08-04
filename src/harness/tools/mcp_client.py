# -*- coding: utf-8 -*-
"""
===============================================================================
[Harness Module 03-MCP Client] Model Context Protocol Client Bridge
-------------------------------------------------------------------------------
Provides standard adapters to connect to standard SQLite MCP server over stdio.
Demonstrates:
1. Static Process Binding: Converting MCP tools into LangChain tools (langchain-mcp-adapters)
2. Dynamic Context Binding: Discovery schemas -> Injection into Prompt -> Context-based invocation
===============================================================================
"""

import os
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm import get_llm

# Auto-load project-level .env file
current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(current_dir, "../../../.env"))


def get_wsl_path(win_path: str) -> str:
    """Converts a standard Windows path into WSL mounting format (/mnt/<drive>/...)"""
    path = win_path.replace("\\", "/")
    if len(path) > 1 and path[1] == ":":
        drive = path[0].lower()
        path = f"/mnt/{drive}{path[2:]}"
    return path


def get_server_parameters() -> StdioServerParameters:
    # Resolve absolute path to the local mcp_server.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_script_win = os.path.join(current_dir, "mcp_server.py")
    server_script_wsl = get_wsl_path(server_script_win)
    
    # Check OS or execution mode to run python under WSL
    return StdioServerParameters(
        command="python",
        args=[server_script_wsl]
    )


# =============================================================================
# 1. Static Process Binding Demo
# =============================================================================
async def run_static_binding_agent_async(user_query: str, model_name: str = "gemini-2.5-pro") -> str:
    server_params = get_server_parameters()
    
    # Establish connection with the MCP server via stdio
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 1. Adapt MCP tools to LangChain StructuredTool objects (Static Process Binding)
            adapted_tools = await load_mcp_tools(session)
            
            # 2. Bind tools directly to the LLM agent instance
            llm = get_llm(model_name=model_name, temperature=0.0)
            llm_with_tools = llm.bind_tools(adapted_tools)
            
            # 3. Simulate React flow (Single turn invocation for demonstration)
            messages = [
                SystemMessage(content="You are an agent with access to local SQLite tables via MCP tools."),
                HumanMessage(content=user_query)
            ]
            
            # LLM decides which tool to call
            response = await asyncio.to_thread(llm_with_tools.invoke, messages)
            
            if response.tool_calls:
                # Find matching adapted tool and execute
                tool_call = response.tool_calls[0]
                t_name = tool_call["name"]
                t_args = tool_call["args"]
                
                target_tool = next((t for t in adapted_tools if t.name == t_name), None)
                if target_tool:
                    observation = await target_tool.ainvoke(t_args)
                    return f"[Static Binding SUCCESS]\nLLM Choice: {t_name}\nArguments: {t_args}\nResult:\n{observation}"
                return f"[Static Binding ERROR] Tool {t_name} not found in adapted set."
            else:
                return f"[Static Binding NO TOOL CALL] LLM response:\n{response.content}"


def run_static_binding_demo(user_query: str, model_name: str = "gemini-2.5-pro") -> str:
    return asyncio.run(run_static_binding_agent_async(user_query, model_name=model_name))


# =============================================================================
# 2. Dynamic Context Binding Demo (Tools as Context)
# =============================================================================
async def run_dynamic_context_agent_async(user_query: str, model_name: str = "gemini-2.5-pro") -> str:
    server_params = get_server_parameters()
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 1. DISCOVERY: Get raw schemas of MCP tools (Dynamic Context discovery)
            mcp_tools_response = await session.list_tools()
            schemas_list = []
            for tool_item in mcp_tools_response.tools:
                schemas_list.append({
                    "name": tool_item.name,
                    "description": tool_item.description,
                    "input_schema": tool_item.inputSchema
                })
            
            # Inject tool descriptions dynamically into the system prompt (Context Binding)
            system_prompt = (
                "You are an agent that interacts with tools via a remote MCP API client.\n"
                "Do NOT attempt to execute tools locally. Instead, output your chosen tool and arguments "
                "in a structured JSON format to be processed by your client wrapper.\n\n"
                f"Available Remote MCP Tools:\n{schemas_list}\n\n"
                "If you need to call a tool, respond with exactly: "
                "CALL_MCP_TOOL: {\"name\": \"tool_name\", \"arguments\": { ... }}"
            )
            
            llm = get_llm(model_name=model_name, temperature=0.0)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_query)
            ]
            
            # Invoke LLM (it will choose and structure the call as text context)
            response = await asyncio.to_thread(llm.invoke, messages)
            resp_content = response.content
            
            if "CALL_MCP_TOOL:" in resp_content:
                # Parse tool invocation command from text context
                try:
                    import json
                    json_str = resp_content.split("CALL_MCP_TOOL:")[1].strip()
                    call_data = json.loads(json_str)
                    t_name = call_data["name"]
                    t_args = call_data["arguments"]
                    
                    # 2. INVOKE: Call the remote tool via Stdio Client request session
                    mcp_result = await session.call_tool(t_name, arguments=t_args)
                    
                    # Read remote result (list of text contents)
                    obs_content = mcp_result.content[0].text if mcp_result.content else ""
                    return (
                        f"[Dynamic Context SUCCESS]\n"
                        f"LLM Decided Contextually: {t_name}\n"
                        f"Arguments: {t_args}\n"
                        f"Remote Invocation Result:\n{obs_content}"
                    )
                except Exception as parse_err:
                    return f"[Dynamic Context Parsing Error]: {parse_err}\nLLM Response was: {resp_content}"
            else:
                return f"[Dynamic Context NO TOOL CALL] LLM response:\n{resp_content}"


def run_dynamic_context_demo(user_query: str, model_name: str = "gemini-2.5-pro") -> str:
    return asyncio.run(run_dynamic_context_agent_async(user_query, model_name=model_name))
