import os
import asyncio
import aiosqlite

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent
from app.utils import get_llm
from app.prompts import CHATBOT_SYSTEM_PROMPT
from app.tools import tools_chatbot
from app.utils.context import AgentContext
from app.middleware.logging_middleware import LoggingMiddleware


# 미들웨어 추가 임포트
from app.middleware.guardrails import InputSafetyGuardrail, TopicAlignmentGuardrail
from app.middleware.self_correction_middleware import tool_call_limit_middleware, smart_context_indexer
from app.middleware.prompt_middleware import harness_agent_prompt_middleware

AGENT_METADATA = {
    "name": "harness_agent",
    "description": "수강생들이 단계별 실무 미션을 통해 완성해나가는 실습용 에이전트"
}

async def create_agent_executor():
    # 1. 일원화된 utils 유틸의 LLM 팩토리 활용
    llm = get_llm(model_name="gemini-3.5-flash", temperature=0.0)
    
    # 2. SQLite 기반의 L1 영속 체크포인터 메모리 구축 (비동기 방식)
    db_dir = "app/database"
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "checkpoints.db")
    
    conn = await aiosqlite.connect(db_path, check_same_thread=False)
    memory = AsyncSqliteSaver(conn)
    await memory.setup()
    
    # 3. 범용 8대 도구(tools_chatbot) 바인딩
    tools = tools_chatbot
    
    # 4. 실시간 수명 주기 로깅, 가드레일, 자가치유, 동적 프롬프트 미들웨어 주입
    logging_middleware = LoggingMiddleware(log_dir="./artifacts/logs")
    middleware = [
        logging_middleware,
        InputSafetyGuardrail(),
        TopicAlignmentGuardrail(),
        smart_context_indexer,
        tool_call_limit_middleware,
        harness_agent_prompt_middleware
    ]
    
    # 5. 에이전트 구축
    harness_agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=None,
        checkpointer=memory,
        middleware=middleware,
        context_schema=AgentContext
    )
    return harness_agent

