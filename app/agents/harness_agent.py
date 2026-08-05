import sqlite3
from langgraph.checkpoint.memory import MemorySaver
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

def get_agent_executor():
    # 1. 일원화된 utils 유틸의 LLM 팩토리 활용
    llm = get_llm(model_name="gemini-3.5-flash", temperature=0.0)
    
    # 2. 대화 세션별 체크포인터 메모리 저장소 셋업
    memory = MemorySaver()
    
    # 3. 범용 8대 도구(tools_chatbot) 바인딩
    tools = tools_chatbot
    
    # 4. 실시간 수명 주기 로깅, 가드레일, 자가치유, 동적 프롬프트 미들웨어 주입
    logging_middleware = LoggingMiddleware(log_dir="./artifacts/logs")
    middleware = [
        logging_middleware,
        # InputSafetyGuardrail(),
        # TopicAlignmentGuardrail(),
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

agent_executor = get_agent_executor()
