# 리눅스 환경에서 시스템 SQLite 버전이 낮을 경우 pysqlite3를 대신 사용하도록 강제함
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import sys
import os
from dotenv import load_dotenv

# 1. Setup Project Root Path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "src"))

# 2. 환경 변수 로드 (.env 파일 명시적 지정)
dotenv_path = os.path.join(project_root, ".env")
if os.path.exists(dotenv_path):
    print(f"Loading .env from: {dotenv_path}")
    load_dotenv(dotenv_path)
    
    # LangSmith Project Setting (Server Specific)
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = "llmops-agent-server"
    print(f"📈 LangSmith Tracing Enabled. Project: {os.environ['LANGSMITH_PROJECT']}")
else:
    print("Warning: .env file not found.")

import logging
import json
import traceback
from typing import AsyncGenerator, Optional, Dict, Any, List

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import importlib
from app.agents import AGENT_REGISTRY
from app.utils.message_utils import sanitize_text, normalize_content
from app.utils.db import create_session, get_sessions, delete_session, add_message, get_messages
from app.utils.context import AgentContext

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMOps_Server")

def load_config(file_path: str, default: dict) -> dict:
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config {file_path}: {e}")
    return default

# --- Schemas ---
class UserInput(BaseModel):
    message: str
    thread_id: Optional[str] = None

class StreamInput(UserInput):
    stream_tokens: bool = Field(default=True)

class ChatMessage(BaseModel):
    type: str
    content: str

class SessionCreate(BaseModel):
    session_id: str
    agent_name: str
    title: str

# --- Router Factory ---
def create_agent_router(agent_executor, prefix: str, tags: list = None) -> APIRouter:
    """
    주어진 에이전트 실행기(Executor)를 위한 FastAPI 라우터를 생성하는 팩토리 함수입니다.
    /invoke 및 /stream 엔드포인트를 자동으로 등록합니다.
    """
    router = APIRouter(prefix=prefix, tags=tags or [prefix])

    async def _stream_generator(input_data: StreamInput) -> AsyncGenerator[str, None]:
        try:
            config = {"configurable": {"thread_id": input_data.thread_id}} if input_data.thread_id else {}
            
            # 런타임에 제어 설정을 동적으로 주입
            logging_cfg = load_config("./configs/logging.config", {"logging_enabled": False, "log_path": "./artifacts/agent_audit_trail.json"})
            hitl_cfg = load_config("./configs/hitl.config", {"hitl_enabled": False})
            
            context_obj = AgentContext(
                logging_enabled=logging_cfg.get("logging_enabled", False),
                log_path=logging_cfg.get("log_path", "./artifacts/agent_audit_trail.json"),
                response_mode="chat",
                hitl_enabled=hitl_cfg.get("hitl_enabled", False),
                debug_mode=os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
            )
            
            # 사용자 메시지 DB 기록
            if input_data.thread_id:
                add_message(input_data.thread_id, "user", input_data.message)
            
            full_response = ""
            
            # LangGraph astream_events (v2)
            async for event in agent_executor.astream_events(
                {"messages": [("user", input_data.message)]}, 
                config=config,
                context=context_obj,
                version="v2"
            ):
                kind = event["event"]
                
                # Tool Start
                if kind == "on_tool_start":
                    tool_input = sanitize_text(str(event['data'].get('input', '')))
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': event['name'], 'input': tool_input})}\n\n"
                
                # Tool End (결과도 함께 전송)
                elif kind == "on_tool_end":
                    tool_output = str(event["data"].get("output", ""))
                    truncated = tool_output[:500] + "..." if len(tool_output) > 500 else tool_output
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': event['name'], 'output': sanitize_text(truncated)})}\n\n"
                
                # Token Streaming (Chat Model)
                elif kind == "on_chat_model_stream":
                    tags = event.get("tags", [])
                    if "exclude_from_stream" in tags:
                        continue

                    chunk = event["data"]["chunk"]
                    if chunk and chunk.content:
                        normalized = sanitize_text(normalize_content(chunk.content))
                        if normalized:
                            full_response += normalized
                            yield f"data: {json.dumps({'type': 'token', 'content': normalized})}\n\n"

            # 어시스턴트 최종 답변 DB 기록
            if not full_response and config:
                try:
                    state = await agent_executor.aget_state(config)
                    messages = state.values.get("messages", []) if state else []
                    if messages:
                        last_msg = messages[-1]
                        from langchain_core.messages import AIMessage
                        if isinstance(last_msg, AIMessage) or getattr(last_msg, "type", None) == "ai":
                            full_response = sanitize_text(normalize_content(last_msg.content))
                            if full_response:
                                yield f"data: {json.dumps({'type': 'token', 'content': full_response})}\n\n"
                except Exception as get_state_err:
                    logger.error(f"Error getting final state: {get_state_err}")

            if input_data.thread_id and full_response:
                add_message(input_data.thread_id, "assistant", full_response)

        except Exception as e:
            logger.error(f"Stream error in {prefix}: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        yield "event: end\ndata: \n\n"

    @router.post("/invoke", response_model=ChatMessage)
    async def invoke(input_data: UserInput):
        try:
            config = {"configurable": {"thread_id": input_data.thread_id}} if input_data.thread_id else {}
            
            # 런타임 제어 설정 생성
            logging_cfg = load_config("./configs/logging.config", {"logging_enabled": False, "log_path": "./artifacts/agent_audit_trail.json"})
            hitl_cfg = load_config("./configs/hitl.config", {"hitl_enabled": False})
            
            context_obj = AgentContext(
                logging_enabled=logging_cfg.get("logging_enabled", False),
                log_path=logging_cfg.get("log_path", "./artifacts/agent_audit_trail.json"),
                response_mode="chat",
                hitl_enabled=hitl_cfg.get("hitl_enabled", False),
                debug_mode=os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
            )
            
            # 사용자 메시지 DB 기록
            if input_data.thread_id:
                add_message(input_data.thread_id, "user", input_data.message)
                
            # invoke returns the final state
            result = await agent_executor.ainvoke(
                {"messages": [("user", input_data.message)]},
                config=config,
                context=context_obj
            )
            last_message = result["messages"][-1]
            normalized = sanitize_text(normalize_content(last_message.content))
            
            # 어시스턴트 답변 DB 기록
            if input_data.thread_id:
                add_message(input_data.thread_id, "assistant", normalized)
                
            return ChatMessage(type="ai", content=normalized)
        except Exception as e:
            logger.error(f"Invocation error in {prefix}: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/stream")
    async def stream(input_data: StreamInput):
        return StreamingResponse(
            _stream_generator(input_data), 
            media_type="text/event-stream"
        )
        
    return router

# --- App Initialization ---
app = FastAPI(
    title="LLMOps Class Agent Server", 
    version="1.0",
    description="Unified Server for Multiple Agents"
)

# --- Chat Session API Endpoints ---
@app.post("/sessions")
def api_create_session(session: SessionCreate):
    try:
        return create_session(session.session_id, session.agent_name, session.title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
def api_get_sessions(agent_name: Optional[str] = None):
    try:
        return get_sessions(agent_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
def api_delete_session(session_id: str):
    try:
        delete_session(session_id)
        return {"status": "success", "deleted_session": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/messages")
def api_get_messages(session_id: str):
    try:
        return get_messages(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Dynamic Agent Registration (Registry 패턴) ---
loaded_agents = []
for agent_config in AGENT_REGISTRY:
    try:
        # 동적으로 모듈 임포트
        module = importlib.import_module(agent_config["module"])
        
        # 에이전트 실행기(executor) 객체 찾기
        executor = getattr(module, "agent_executor", None)
        if not executor:
            executor_factory = getattr(module, f"create_{agent_config['name']}_agent", None)
            if executor_factory:
                executor = executor_factory()
                
        if executor:
            app.include_router(
                create_agent_router(executor, agent_config["prefix"], agent_config["tags"])
            )
            loaded_agents.append(agent_config["name"])
            logger.info(f"✅ Registered agent: {agent_config['name']} at {agent_config['prefix']}")
        else:
            logger.warning(f"⚠️ Warning: '{agent_config['name']}' 모듈에 'agent_executor'가 없습니다.")
    except Exception as e:
        logger.error(f"❌ Failed to load agent '{agent_config['name']}': {e}")
        traceback.print_exc()

@app.get("/health")
def health():
    return {"status": "ok", "agents": loaded_agents}

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Server Port")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server Host")
    args = parser.parse_args()
    
    print(f"🚀 Server starting on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
