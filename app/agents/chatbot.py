"""
app/agents/chatbot.py — 기본 4대 하네스 + Mission 01 커스텀 도구 기준 완성본

[하네스 4대 기본 요소]
1. 에이전트 프로필: AGENT_METADATA (UI 드롭다운 및 레지스트리)
2. 시스템 프롬프트: CHATBOT_SYSTEM_PROMPT (고양이 페르소나 및 파일 규칙)
3. 단기 기억: AsyncSqliteSaver (세션/스레드별 대화 히스토리 영속 저장)
4. 도구: active_tools (범용 10대 도구 + [Mission 01] roll_dice, convert_currency)
"""

import os
import json
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent
from app.utils import init_chat_model
from app.prompts import CHATBOT_SYSTEM_PROMPT
from app.tools import tools_chatbot
from app.tools.custom_tools import roll_dice, convert_currency
from app.utils.context import AgentContext

# 1. 에이전트 프로필
AGENT_METADATA = {
    "name": "chatbot",
    "description": "기본 4대 하네스와 커스텀 도구(주사위/환율)가 완결 탑재된 고양이 챗봇"
}


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
    
    # 4. 도구 바인딩 (범용 10대 도구 + Mission 01 커스텀 도구 2종 결합)
    active_tools = list(tools_chatbot) + [roll_dice, convert_currency]
    
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
