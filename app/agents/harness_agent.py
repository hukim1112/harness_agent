from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from app.utils import get_llm
from app.prompts import CHATBOT_SYSTEM_PROMPT
from app.tools import tools_chatbot
from app.utils.context import AgentContext
# TODO: Mission 02 - SQLite 체크포인터 임포트
# from langgraph.checkpoint.sqlite import SqliteSaver
# TODO: Mission 04 - 로깅 미들웨어 임포트
# from harness.monitoring import LoggingMiddleware

def get_agent_executor():
    # 1. 일원화된 utils 유틸의 LLM 팩토리 활용 (openai: 접두사로 공급자 강제 매칭)
    llm = get_llm(model_name="openai:gpt-4o", temperature=0.0)
    
    # TODO: Mission 02 - 임시 MemorySaver 대신 SqliteSaver로 영속 체크포인터 구축하기
    memory = MemorySaver()
    
    # TODO: Mission 03 - 범용 8대 도구(tools_chatbot)를 바인딩하여 ReAct 루프 완성하기
    # (Mission 01에서는 빈 리스트 []로 시작합니다)
    tools = []
    
    # TODO: Mission 04 - 실시간 모니터링을 위한 LoggingMiddleware 등록하기
    middleware = []
    
    # 3. 에이전트 구축
    harness_agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=CHATBOT_SYSTEM_PROMPT,
        checkpointer=memory,
        middleware=middleware,
        context_schema=AgentContext
    )
    return harness_agent

agent_executor = get_agent_executor()
