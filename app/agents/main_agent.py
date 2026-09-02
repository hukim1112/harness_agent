"""
app/agents/main_agent.py — 메인 오케스트레이터 에이전트 (실습 스타터)

교육생은 missions/ 가이드의 안내에 따라 이 파일에 하네스 기능을 순서대로 결합해 나갑니다.
- Mission 02: 자가 복구(Self-Recovery) 미들웨어 & 오케스트레이션 도구 장착
- Mission 03: 5계층 프롬프트 조립기 & 계층형 메모리(Semantic/Episodic) 결합
"""

import os
import json
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent

from app.utils import init_chat_model
from app.utils.context import AgentContext
from app.prompts import SUPERVISOR_SYSTEM_PROMPT

# 1. 에이전트 프로필
AGENT_METADATA = {
    "name": "main_agent",
    "description": "하네스 기능을 연결할 메인 오케스트레이터 에이전트"
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

    # 3. L1 단기 기억 (SQLite 기반 세션 체크포인터)
    db_dir = "app/database"
    os.makedirs(db_dir, exist_ok=True)
    checkpoints_path = os.path.join(db_dir, "checkpoints.db")

    conn = await aiosqlite.connect(checkpoints_path, check_same_thread=False)
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()

    # 4. 미들웨어 파이프라인 (Mission 02에서 Self-Recovery 미들웨어 추가)
    middleware = []

    # 5. 도구 바인딩 (Mission 02에서 tools_supervisor 연결)
    active_tools = []

    # 6. 하네스로 결합된 최종 메인 에이전트 인스턴스 구축
    main_agent = create_agent(
        model=llm,
        tools=active_tools,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )

    main_agent.registered_tools = active_tools
    main_agent.checkpointer_conn = conn
    return main_agent
