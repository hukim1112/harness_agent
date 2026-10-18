"""
app/agents/main_agent/agent.py — 메인 오케스트레이터 에이전트 (실습 스타터)

교육생은 missions/ 가이드의 안내에 따라 이 파일에 하네스 기능을 순서대로 결합해 나갑니다.
- Mission 02: 자가 복구(Self-Recovery) 미들웨어 & 오케스트레이션 도구 장착
- Mission 03: 5계층 프롬프트 조립기 & 계층형 메모리(Semantic/Episodic) 결합
- Mission 04: 전문 금융 스킬(10종) 카탈로그 동적 주입
- Mission 05: Human-in-the-Loop 권한 승인 게이트 장착
- Mission 06: 입력 보안 & 주제 정렬 가드레일 장착
- Mission 07: 비동기 JSONL 감사 로깅(AgentLogTracer) 장착
"""

import os
import json
from pathlib import Path
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent

from app.utils import init_chat_model
from app.utils.context import AgentContext
from .prompt import SUPERVISOR_SYSTEM_PROMPT
from .tools import tools_supervisor

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# 1. 에이전트 프로필
AGENT_METADATA = {
    "name": "main_agent",
    "description": "하네스 기능을 연결할 메인 오케스트레이터 에이전트",
    "roles": ["main"],  # main: UI 대화 전용 (서브에이전트 위임 대상 제외)
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


async def create_agent_executor(checkpointer=None):
    # 2. LLM 초기화 (configs/model.config 기반)
    model_cfg = _load_config("./configs/model.config", {
        "model_name": "gemini-3.8-flash",
        "temperature": 0.0,
    })
    llm = init_chat_model(
        model=model_cfg.get("model_name", "gemini-3.8-flash"),
        temperature=model_cfg.get("temperature", 0.0)
    )

    # 3. L1 단기 기억 (SQLite 기반 세션 체크포인터)
    db_dir = "app/database"
    os.makedirs(db_dir, exist_ok=True)
    checkpoints_path = os.path.join(db_dir, "checkpoints.db")

    conn = None
    if checkpointer is None:
        conn = await aiosqlite.connect(checkpoints_path, check_same_thread=False)
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        checkpointer = AsyncSqliteSaver(conn)
        await checkpointer.setup()

    # 4. 미들웨어 파이프라인
    #    - Mission 02: Self-Recovery 3종 (ModelFallback, ToolErrorHandler, ModelCallLimit)
    #    - Mission 03: MemoryMiddleware, PromptAssemblerMiddleware
    #    - Mission 05: HumanInTheLoopMiddleware (configs/hitl.config)
    #    - Mission 06: InputSafetyGuardrail, TopicAlignmentGuardrail (configs/guardrail.config)
    #    - Mission 07: AgentLogTracer (configs/logging.config)
    #    ※ 전체 순서는 missions/MIDDLEWARE_PIPELINE_REFERENCE.md 참고:
    #       [1.Logging] -> [2.Guardrails] -> [3.Memory & Prompt] -> [4.HITL] -> [5.Self-Recovery]
    middleware = []

    # 5. 도구 바인딩
    #    - Mission 02: list(tools_supervisor)
    #    - Mission 03: list(tools_supervisor) + [roll_dice, convert_currency]
    #      (※ memory, session_recall 도구는 MemoryMiddleware가 create_agent에 자동 등록)
    active_tools = []

    # 6. 하네스로 결합된 최종 메인 에이전트 인스턴스 구축
    #    (※ Mission 03부터는 PromptAssemblerMiddleware가 프롬프트를 주입하므로 system_prompt 인자를 제거합니다)
    main_agent = create_agent(
        model=llm,
        tools=active_tools,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )

    main_agent.registered_tools = active_tools
    main_agent.registered_middlewares = middleware
    main_agent.checkpointer_conn = conn
    return main_agent
