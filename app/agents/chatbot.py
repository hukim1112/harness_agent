"""
app/agents/chatbot.py — 3대 코어 요소 및 서비스 메타데이터가 탑재된 챗봇 에이전트

[하네스 구성 요소]
1. 코어 3요소: 프롬프트(CHATBOT_SYSTEM_PROMPT), 도구(active_tools), 단기기억(AsyncSqliteSaver)
2. 서비스 인터페이스: AGENT_METADATA (UI 프로필 및 FastAPI 레지스트리)
"""

import os
import json
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent
from app.utils import init_chat_model
from app.prompts import CHATBOT_SYSTEM_PROMPT
from app.tools import tools_chatbot
from app.utils.context import AgentContext

# -------------------------------------------------------------------------------
# 1. 서비스 메타데이터 (FastAPI 레지스트리 및 Chainlit UI ChatProfile 자동 등록)
# -------------------------------------------------------------------------------
AGENT_METADATA = {
    "name": "chatbot",
    "description": "3대 코어(프롬프트, 도구, 단기메모리)가 탑재된 친근한 고양이 챗봇"
}

# -------------------------------------------------------------------------------
# 🎯 [Mission 01 실습 안내]
# 1단계에서 app/tools/custom_tools.py에 작성한 도구를 여기에 임포트하세요.
# 예시: from app.tools.custom_tools import roll_dice, convert_currency
# -------------------------------------------------------------------------------
# from app.tools.custom_tools import ...


def _load_config(path: str, default: dict) -> dict:
    """설정 파일을 로드합니다. 실패 시 기본값을 반환합니다."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


async def create_agent_executor():
    # 2. LLM 초기화 (configs/model.config 기반)
    model_cfg = _load_config("./configs/model.config", {
        "model_name": "gemini-3.7-flash",
        "temperature": 0.0,
    })
    llm = init_chat_model(
        model=model_cfg.get("model_name", "gemini-3.7-flash"),
        temperature=model_cfg.get("temperature", 0.0)
    )
    
    # 3. 단기 기억 (SQLite 기반 대화 세션 체크포인터)
    db_dir = "app/database"
    os.makedirs(db_dir, exist_ok=True)
    checkpoints_path = os.path.join(db_dir, "checkpoints.db")

    conn = await aiosqlite.connect(checkpoints_path, check_same_thread=False)
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()
    
    # ---------------------------------------------------------------------------
    # 4. 도구 바인딩
    # 🎯 [Mission 01 실습 안내]
    # custom_tools에서 임포트한 도구를 active_tools 리스트에 결합하세요.
    # 예시: active_tools = list(tools_chatbot) + [roll_dice, convert_currency]
    # ---------------------------------------------------------------------------
    active_tools = list(tools_chatbot)
    
    # 5. 하네스로 결합된 최종 에이전트 인스턴스 구축
    chatbot_agent = create_agent(
        model=llm,
        tools=active_tools,
        system_prompt=CHATBOT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
        context_schema=AgentContext
    )

    chatbot_agent.registered_tools = active_tools
    chatbot_agent.checkpointer_conn = conn
    return chatbot_agent
