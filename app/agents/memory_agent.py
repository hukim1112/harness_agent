"""
===============================================================================
Memory-Enabled Production Agent (memory_agent)
===============================================================================
Claude Code 표준 5계층 프롬프트 스택 + 계층형 메모리(Semantic & Episodic)가 탑재된 에이전트

특징:
1. 5-Layer Prompt Stack: L1(Identity) ~ L2(Tools/Skills) ~ L3(Session) ~ L4(Memory) ~ L5(Project Rules)
2. Semantic Memory: MEMORY.md / USER.md 마크다운 장기 기억 + Frozen Snapshot
3. Episodic Memory: SQLite FTS5 세션 요약 인출 + JIT session_recall 도구
4. Dynamic Memory Middleware: before_agent 힌트 주입 + after_agent 백그라운드 학습
===============================================================================
"""

import os
import json
import aiosqlite
from typing import Dict, Any, Optional, List, Union
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent

from app.utils import init_chat_model
from app.utils.context import AgentContext
from app.tools import tools_chatbot
from app.middleware.memory import SemanticMemoryStore, EpisodicStore, MemoryMiddleware
from app.middleware.prompt import PromptAssembler, create_prompt_assembler_middleware
from app.middleware.observability import LoggingMiddleware

AGENT_METADATA = {
    "name": "memory_agent",
    "description": "5계층 프롬프트 및 계층형 메모리(Semantic/Episodic)가 탑재된 장기 기억 에이전트"
}

DEFAULT_SYSTEM_RULES = """You are an advanced AI Software Engineer equipped with long-term memory and precise reasoning capabilities.
- Analyze user requests carefully and utilize past context and personal preferences when available.
- For managing long-term knowledge, you can use the 'memory' tool to record important facts about the user or environment.
- When past session summaries are provided in your context, use the 'session_recall' tool to retrieve specific messages if details are needed.
- Always provide clear, structured, and accurate responses.
"""


def _load_config(file_path: str, default: dict) -> dict:
    """설정 파일을 안전하게 로드합니다."""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


async def create_agent_executor():
    """Memory-enabled 에이전트 실행기를 생성합니다. (configs/model.config & configs/memory.config 기반)"""
    # 1. Configs 로드
    model_cfg = _load_config("./configs/model.config", {
        "model_name": "gemini-3.7-flash",
        "temperature": 0.0,
    })
    mem_cfg = _load_config("./configs/memory.config", {
        "checkpoint_db_path": "./app/database/checkpoints.db",
        "semantic_memory": {
            "enabled": True,
            "memory_dir": "./app/database",
            "user_path": "./app/database/USER.md",
            "memory_path": "./app/database/MEMORY.md",
            "auto_review": True
        },
        "episodic_memory": {
            "enabled": True,
            "db_path": "./artifacts/memory/episodic.db",
            "top_k_prefetch": 2,
            "auto_finalize": True
        }
    })
    log_cfg = _load_config("./configs/logging.config", {"logging_enabled": False})

    # 2. LLM 초기화 (model.config 기반)
    model_name = model_cfg.get("model_name", "gemini-3.7-flash")
    temperature = model_cfg.get("temperature", 0.0)
    llm = init_chat_model(model=model_name, temperature=temperature)

    # 3. Semantic Memory Store 초기화
    sem_cfg = mem_cfg.get("semantic_memory", {})
    effective_mem_dir = sem_cfg.get("memory_dir") or os.path.dirname(sem_cfg.get("memory_path", "./app/database/MEMORY.md")) or "./app/database"
    os.makedirs(effective_mem_dir, exist_ok=True)

    semantic_store = SemanticMemoryStore(
        memory_dir=effective_mem_dir,
        memory_char_limit=4000,
        user_char_limit=2000,
    )
    if sem_cfg.get("enabled", True):
        semantic_store.load_from_disk()

    # 4. Episodic Memory Store 초기화
    epi_cfg = mem_cfg.get("episodic_memory", {})
    effective_db_path = epi_cfg.get("db_path", "./artifacts/memory/episodic.db")
    os.makedirs(os.path.dirname(os.path.abspath(effective_db_path)), exist_ok=True)
    episodic_store = EpisodicStore(db_path=effective_db_path)
    await episodic_store.setup()

    # 5. Memory Middleware 구성 (스토어 + 도구 + before/after 훅)
    memory_mw = MemoryMiddleware(
        semantic_store=semantic_store,
        episodic_store=episodic_store,
        review_llm=llm if sem_cfg.get("auto_review", True) else None,
    )
    memory_tools = memory_mw.get_tools()

    # 6. 전체 도구 세트 조립 (기본 챗봇 도구 + 메모리 전용 도구)
    all_tools = list(tools_chatbot) + memory_tools

    # 7. Claude Code 표준 5-Layer Prompt Assembler 구성
    #
    # ⚠️ 설계 원칙: Semantic Memory (USER.md / MEMORY.md) 주입 경로 단일화
    # ────────────────────────────────────────────────────────────────────
    # Semantic Memory는 PromptAssembler.l4_docs에 등록하지 않습니다.
    # 대신 MemoryMiddleware.before_agent()가 세션 시작 시 Frozen Snapshot을
    # ctx.recalled_memory에 주입하고, PromptAssembler가 이를 L4에 반영합니다.
    #
    # 주입 경로:
    #   MemoryMiddleware.before_agent()
    #     → semantic_store.load_from_disk() (세션 전환 시 1회)
    #     → semantic_store.format_for_prompt("memory" | "user")
    #     → ctx.recalled_memory에 Frozen Snapshot 합류
    #   PromptAssembler.build_dynamic_content()
    #     → session_context["recalled_memory"] 읽기
    #     → L4 "[Recalled Memory]" 블록에 출력
    #
    # 이렇게 하면:
    #   1. 토큰 이중 소모 방지 (l4_docs + recalled_memory 중복 제거)
    #   2. Frozen Snapshot 보장 (세션 중 MEMORY.md 변경되어도 프롬프트 불변)
    #   3. 캐시 안정성 유지 (동적 부분은 ctx.recalled_memory 한 곳에서만 변동)
    # ────────────────────────────────────────────────────────────────────

    # L4에는 MCP.md 등 비메모리 동적 문서만 등록 (USER.md/MEMORY.md는 MemoryMiddleware 경유)
    l4_docs = {}

    # 스킬 디렉토리 스캔 및 Frontmatter 카탈로그 조립기
    from app.middleware.prompt import SkillPromptBuilder
    skill_builder = SkillPromptBuilder(
        skills_dirs=["./skills", "./.agents/skills", "skills", "../skills", os.path.join(os.getcwd(), "skills")],
        guidelines_path="app/prompts/SKILL.md" if os.path.exists("app/prompts/SKILL.md") else None,
    )

    assembler = PromptAssembler(
        system_rules=DEFAULT_SYSTEM_RULES,
        tool_schemas=all_tools,
        skill_catalog=skill_builder.assemble,
        l4_docs=l4_docs,
        agent_rules_path="app/prompts/SKILL.md" if os.path.exists("app/prompts/SKILL.md") else None,
    )

    # Gemini/OpenAI 호환을 위해 merge_system=True (또는 Anthropic인 경우 False)
    prompt_mw = create_prompt_assembler_middleware(assembler, merge_system=True)

    # 8. 미들웨어 파이프라인 구성
    middleware = []
    if log_cfg.get("logging_enabled", False):
        middleware.append(LoggingMiddleware(log_path=log_cfg.get("log_path", "./artifacts/agent_audit_trail.json")))
    
    # ⚠️ 중요: MemoryMiddleware가 PromptAssembler보다 먼저 실행되어야 recalled_memory가 L4에 반영됨
    middleware.append(memory_mw)
    middleware.append(prompt_mw)

    # 9. SQLite Checkpointer 연결
    checkpoints_path = mem_cfg.get("checkpoint_db_path", "app/database/checkpoints.db")
    os.makedirs(os.path.dirname(os.path.abspath(checkpoints_path)), exist_ok=True)
    conn = await aiosqlite.connect(checkpoints_path, check_same_thread=False)
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()

    # 10. Agent 생성
    agent = create_agent(
        model=llm,
        tools=all_tools,
        middleware=middleware,
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )

    # 리소스 정리를 위한 참조 저장
    agent.registered_tools = all_tools
    agent.checkpointer_conn = conn
    agent.episodic_store = episodic_store
    agent.semantic_store = semantic_store
    agent.assembler = assembler

    return agent
