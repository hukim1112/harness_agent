from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from app.utils import get_llm
from app.prompts import CHATBOT_SYSTEM_PROMPT
from app.tools import tools_chatbot
from app.utils.context import AgentContext
from app.middleware.reference_logging import ReferenceLoggingMiddleware as LoggingMiddleware

def get_agent_executor():
    # 1. 일원화된 utils 유틸의 LLM 팩토리 활용 (openai: 접두사로 공급자 강제 매칭)
    llm = get_llm(model_name="openai:gpt-4o", temperature=0.0)
    
    # 2. 대화 세션별 체크포인터 메모리 저장소 셋업
    memory = MemorySaver()
    
    # 3. 로깅 미들웨어 등록 (서버 실행 시 로그 적재 활성화 지원)
    logging_middleware = LoggingMiddleware()
    
    # 4. 범용 8대 도구가 탑재된 스마트 챗봇 에이전트 구축
    chatbot_agent = create_agent(
        model=llm,
        tools=tools_chatbot,
        system_prompt=CHATBOT_SYSTEM_PROMPT,
        checkpointer=memory,
        middleware=[logging_middleware],
        context_schema=AgentContext
    )
    return chatbot_agent

agent_executor = get_agent_executor()
