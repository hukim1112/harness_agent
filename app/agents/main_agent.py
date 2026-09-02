"""
app/agents/main_agent.py — 자가 복구, 서브에이전트 오케스트레이션, 5계층 프롬프트 및 계층형 메모리 하네스 완성본

[하네스 구성]
1. 에이전트 프로필: AGENT_METADATA (main_agent)
2. 5-Layer Prompt Stack (Claude Code 표준):
   - L1: System Rules & Identity (SUPERVISOR_SYSTEM_PROMPT: 5-Phase 오케스트레이션 루프)
   - L2: Capabilities (도구 스키마 및 skills/ 카탈로그)
   - L3: Dynamic Session Context (CWD, Session ID, Current Date, Host OS)
   - L4: Recalled Memory (Frozen Semantic Memory 스냅샷 + Episodic 과거 세션 요약 힌트)
   - L5: Project Rules & Guidelines
3. 계층형 메모리 (Layered Memory):
   - L1 단기 기억: AsyncSqliteSaver (세션별 체크포인터)
   - L2 에피소드 기억: EpisodicStore (SQLite FTS5 + finalize_session + session_recall JIT 인출)
   - L3 시맨틱 기억: SemanticMemoryStore (USER.md / MEMORY.md + memory 도구)
4. Self-Recovery 미들웨어:
   - ModelFallbackMiddleware: LLM 장애 시 백업 모델로 failover
   - ToolErrorHandlerMiddleware: 도구 예외 시 ToolMessage(Observation)로 변환
   - ModelCallLimitMiddleware: 무한 루프 차단 (run_limit=50)
5. 도구: tools_supervisor(14종) + memory_tools(2종: memory, session_recall) = 총 16종
"""

import os
import json
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware

from app.utils import init_chat_model
from app.utils.context import AgentContext
from app.prompts import SUPERVISOR_SYSTEM_PROMPT
from app.tools import tools_supervisor
from app.tools.custom_tools import roll_dice, convert_currency
from app.middleware.memory import SemanticMemoryStore, EpisodicStore, MemoryMiddleware
from app.middleware.prompt import PromptAssembler, SkillPromptBuilder, create_prompt_assembler_middleware
from app.middleware.error_control.self_recovery import (
    ModelFallbackMiddleware,
    ToolErrorHandlerMiddleware,
    ModelCallLimitMiddleware,
)
from app.middleware.guardrails import InputSafetyGuardrail, TopicAlignmentGuardrail
from app.middleware.observability import AgentLogTracer

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

    # 4. L3 Semantic Memory Store 초기화 (MEMORY.md / USER.md)
    semantic_store = SemanticMemoryStore(
        memory_dir=db_dir,
        memory_char_limit=4000,
        user_char_limit=2000,
    )
    semantic_store.load_from_disk()

    # 5. L2 Episodic Memory Store 초기화 (과거 세션 대화 + SQLite FTS5 인덱싱)
    episodic_db_dir = "artifacts/memory"
    os.makedirs(episodic_db_dir, exist_ok=True)
    episodic_db_path = os.path.join(episodic_db_dir, "episodic.db")
    episodic_store = EpisodicStore(db_path=episodic_db_path)
    await episodic_store.setup()

    # 6. MemoryMiddleware 구성 (스토어 + memory / session_recall 도구 + 훅)
    memory_mw = MemoryMiddleware(
        semantic_store=semantic_store,
        episodic_store=episodic_store,
        review_llm=llm,
    )
    memory_tools = memory_mw.get_tools()

    # 7. 전체 도구 세트 통합 (Supervisor 15종 + Memory 2종 + Custom 2종 = 19종)
    active_tools = list(tools_supervisor) + list(memory_tools) + [roll_dice, convert_currency]

    # 8. Claude Code 표준 5-Layer Prompt Assembler 구성
    skill_builder = SkillPromptBuilder(
        skills_dirs=["./skills", "./.agents/skills", "skills", os.path.join(os.getcwd(), "skills")],
        guidelines_path="app/prompts/SKILL.md" if os.path.exists("app/prompts/SKILL.md") else None,
    )

    assembler = PromptAssembler(
        system_rules=SUPERVISOR_SYSTEM_PROMPT,
        tool_schemas=active_tools,
        skill_catalog=skill_builder.assemble,
        l4_docs={},
        agent_rules_path="app/prompts/SKILL.md" if os.path.exists("app/prompts/SKILL.md") else None,
    )
    prompt_mw = create_prompt_assembler_middleware(assembler, merge_system=True)

    # 9. 통합 미들웨어 파이프라인 (보안 & 거버넌스 파이프라인 순서)
    middleware = []

    # (1) Logging & Observability (AgentLogTracer)
    logging_cfg = _load_config("./configs/logging.config", {"logging_enabled": False})
    if logging_cfg.get("logging_enabled"):
        log_dir = logging_cfg.get("log_dir", "./artifacts/logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "agent_audit_trail.json")
        middleware.append(AgentLogTracer(log_path=log_path))

    # (2) Guardrails (InputSafety & TopicAlignment)
    guardrail_cfg = _load_config("./configs/guardrail.config", {"guardrail_enabled": False})
    if guardrail_cfg.get("guardrail_enabled"):
        guard_model = model_cfg.get("model_name", "gemini-2.5-flash")
        if guardrail_cfg.get("input_safety", {}).get("enabled", True):
            middleware.append(InputSafetyGuardrail(model=guard_model, fail_mode="open"))
        if guardrail_cfg.get("topic_alignment", {}).get("enabled", True):
            blocked = guardrail_cfg.get("topic_alignment", {}).get("blocked_topics")
            middleware.append(TopicAlignmentGuardrail(model=guard_model, blocked_topics=blocked, fail_mode="open"))

    # (3) Memory & Prompt Assembler
    middleware.extend([memory_mw, prompt_mw])

    # (4) Human-in-the-Loop (roll_dice 타깃 권한 게이트)
    hitl_cfg = _load_config("./configs/hitl.config", {"hitl_enabled": False})
    if hitl_cfg.get("hitl_enabled"):
        interrupt_on = hitl_cfg.get("interrupt_on", {})
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # (5) Self-Recovery Circuit Breakers
    backup_model = os.getenv("FALLBACK_MODEL_NAME", "gemini-2.5-flash")
    middleware.extend([
        ModelFallbackMiddleware(
            max_retries=2,
            initial_delay=0.5,
            fallback_model_name=backup_model
        ),
        ToolErrorHandlerMiddleware(max_retries=0),
        ModelCallLimitMiddleware(run_limit=50, exit_behavior="end"),
    ])

    # 10. 하네스로 결합된 최종 메인 에이전트 인스턴스 구축
    main_agent = create_agent(
        model=llm,
        tools=active_tools,
        middleware=middleware,
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )

    # 리소스 정리 및 검증용 참조 보존
    main_agent.registered_tools = active_tools
    main_agent.checkpointer_conn = conn
    main_agent.episodic_store = episodic_store
    main_agent.semantic_store = semantic_store
    main_agent.assembler = assembler
    main_agent.memory_middleware = memory_mw

    return main_agent
