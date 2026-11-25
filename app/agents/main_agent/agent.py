"""
app/agents/main_agent/agent.py — 메인 오케스트레이터 에이전트 (Instructor 완성본)

교육생이 Mission 00~07을 순서대로 완수한 구성에 Context Compaction 및 StopHooksMiddleware를 추가한 완성본입니다.

패키지 구조:
  app/agents/main_agent/
   ├── agent.py       (에이전트 조립 및 10단계 / 11개 인스턴스 미들웨어 파이프라인)
   ├── prompt.py      (SUPERVISOR_SYSTEM_PROMPT — 정적 SystemMessage)
   ├── tools.py       (계획 5종 + 오케스트레이션 4종 + 공통 8종 = 17종 도구 바인딩)
   └── skills/        (에이전트 내재화 스킬 — User Context 카탈로그 & Delta로 노출)

[하네스 구성 요소]
1. 에이전트 프로필 (AGENT_METADATA)
2. 프롬프트 조립 구조 (단순화된 Claude Code 캐시 우선 구조):
   - ① Tool Specification : API tools 필드 (create_agent 자동 바인딩 + 이름순 정렬)
   - ② System Message     : 정적 SUPERVISOR_SYSTEM_PROMPT (cache_control: ephemeral)
   - ③ User Context       : 대화 맨 앞 <system-reminder> (세션 · 스킬 지침/카탈로그 · Semantic 동결 스냅샷)
   - ④ Conversation + Δ   : 대화 메시지 + 꼬리 <system-reminder> (Skill 양방향 Delta · 자정 날짜 변경)
3. 계층형 메모리 (Layered Memory & Dual-Tier Session Data):
   - L1 단기 기억  : AsyncSqliteSaver (세션별 체크포인터 — SummarizationMiddleware가 이전 대화를 요약본으로 교체)
   - L2 에피소드 원문: TranscriptStore (transcript.db — 대화·도구 호출/결과 실시간 Append-only 백업)
   - L2 에피소드 색인: EpisodicStore (episodic.db — 다중 주제 요약·키워드 SQLite FTS5 + session_search/session_recall 2단계 도구 인출)
   - L3 시맨틱 기억 : SemanticMemoryStore (USER.md / MEMORY.md + memory 도구)
4. Self-Recovery & Self-Correction 미들웨어:
   - ModelFallbackMiddleware    : LLM 장애 시 백업 모델로 failover (413 토큰 초과는 상위로 전파)
   - ToolErrorHandlerMiddleware : 도구 예외 시 ToolMessage(Observation)로 변환
   - ModelCallLimitMiddleware   : 무한 루프 차단 (run_limit=50)
   - StopHooksMiddleware        : 생성된 Python 코드블록 AST 구문 검증 및 자가 교정 루프
5. 도구: tools_supervisor(17종) + memory_tools(3종: memory, session_search, session_recall) + custom_tools(CUSTOM_TOOLS, 기본 roll_dice 1종+) = 총 21종+

[미들웨어 파이프라인 실행 순서]
   사용자 요청 →
     [1] AgentLogTracer            ← 가장 바깥: 차단 포함 전체 라이프사이클 감사 로깅
     [2] InputSafetyGuardrail      ← before_agent: 프롬프트 인젝션/탈옥 시도 선제 차단 (jump_to="end")
     [3] MemoryMiddleware          ← before_agent(원문 기록 & L3 시맨틱 스냅샷 프리페치) + wrap_model/tool(원문 기록 & 도구 필터링) + after_agent(유휴 리뷰 예약)
     [4] Compaction (2개 인스턴스) ← ToolResultSwapMiddleware(wrap_tool_call: 대형 도구 결과 디스크 Swap)
                                    + SummarizationMiddleware(before_model: trigger 초과 시 이전 대화 요약)
     [5] PromptAssemblerMiddleware ← before_model(날짜/스킬Delta 알림) + wrap_model_call(정적 System + User Context + 도구 정렬)
     [6] HumanInTheLoopMiddleware  ← 도구 실행 직전 사용자 승인 요청
     [7] ModelFallbackMiddleware   ← 모델 호출 실패 시 백업 모델로 재시도
     [8] ToolErrorHandlerMiddleware← 도구 실행 오류 시 에러 메시지로 변환
     [9] ModelCallLimitMiddleware  ← 무한 루프 방지 (최대 호출 횟수 제한)
    [10] StopHooksMiddleware       ← after_model: 코드 구문 에러 시 jump_to="model" 자가 교정
                                  → LLM 모델 호출
"""

import os
import json
from pathlib import Path
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware

from app.utils import init_chat_model
from app.utils.database import get_shared_checkpointer
from app.context import AgentContext

from .prompt import SUPERVISOR_SYSTEM_PROMPT
from .tools import tools_supervisor

# Mission 01: ACI 커스텀 도구 (CUSTOM_TOOLS — 기본 roll_dice + 선택 자유 도구)
from app.tools.custom_tools import CUSTOM_TOOLS, roll_dice

# Mission 03: 계층형 메모리 + 5계층 프롬프트 조립기
from app.middleware.memory import (
    SemanticMemoryStore,
    EpisodicStore,
    TranscriptStore,
    MemoryMiddleware,
)
from app.middleware.prompt import PromptAssembler, SkillPromptBuilder, create_prompt_assembler_middleware

# Mission 02: Self-Recovery & Self-Correction 미들웨어
from app.middleware.error_control.self_recovery import (
    ModelFallbackMiddleware,
    ToolErrorHandlerMiddleware,
    ModelCallLimitMiddleware,
)
from app.middleware.error_control.self_correction import StopHooksMiddleware

# Context Compaction: 대형 도구 결과 Swap + SummarizationMiddleware
from app.middleware.compaction import create_compaction_middleware

# Mission 06: 입력 보안 가드레일
from app.middleware.guardrails import InputSafetyGuardrail

# Mission 07: 비동기 감사 로깅 (AgentLogTracer)
from app.middleware.observability import AgentLogTracer

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

    # 3. L1 단기 기억 (공유 SQLite 체크포인터 SSOT)
    if checkpointer is None:
        checkpointer = await get_shared_checkpointer()

    # 4. 도구 바인딩 (Supervisor 17종 + Custom 도구 / Memory 3종은 memory_mw가 자동 등록 → 총 21종+)
    custom_tools_list = list(CUSTOM_TOOLS)
    if not any(getattr(t, "name", "") == getattr(roll_dice, "name", "roll_dice") for t in custom_tools_list):
        custom_tools_list.append(roll_dice)
    active_tools = list(tools_supervisor) + custom_tools_list

    # 4-1. 메모리 설정 로드 (configs/memory.config)
    memory_cfg = _load_config("./configs/memory.config", {})
    sem_cfg = memory_cfg.get("semantic_memory", {})
    epi_cfg = memory_cfg.get("episodic_memory", {})
    tr_cfg = memory_cfg.get("transcript", {})

    # 4-2. L3 Semantic Memory Store 초기화 (USER.md, MEMORY.md)
    #    기본값 artifacts/users/default/memory → 사용자별 artifacts/users/{user_id}/memory/ 자동 격리
    memory_dir = sem_cfg.get("memory_dir", "./artifacts/users/default/memory")
    os.makedirs(memory_dir, exist_ok=True)
    semantic_store = SemanticMemoryStore(
        memory_dir=memory_dir,
        memory_char_limit=4000,
        user_char_limit=2000,
    )
    semantic_store.load_from_disk()

    # 4-3. L2 원문 저장소(TranscriptStore) + 요약 색인(EpisodicStore) 초기화
    transcript_db_path = tr_cfg.get("db_path", "./app/database/transcript.db")
    os.makedirs(os.path.dirname(transcript_db_path) or ".", exist_ok=True)
    transcript_store = TranscriptStore(
        db_path=transcript_db_path,
        recall_max_chars=int(tr_cfg.get("recall_max_chars", 2000)),
    )
    await transcript_store.setup()

    episodic_db_path = epi_cfg.get("db_path", "./app/database/episodic.db")
    os.makedirs(os.path.dirname(episodic_db_path) or ".", exist_ok=True)
    episodic_store = EpisodicStore(
        db_path=episodic_db_path,
        transcript_store=transcript_store,
    )
    await episodic_store.setup()

    # 4-4. MemoryMiddleware 구성 (스토어 + memory / session_search / session_recall 도구 자동 등록 + 원문 기록 + 유휴 요약 훅)
    memory_mw = MemoryMiddleware(
        semantic_store=semantic_store,
        episodic_store=episodic_store,
        review_llm=llm,
        top_k=epi_cfg.get("top_k_prefetch", 2),
        transcript_store=transcript_store,
        transcript_enabled=tr_cfg.get("enabled", True),
        finalize_idle_settle_s=float(epi_cfg.get("finalize_idle_settle_s", 15.0)),
        finalize_max_age_s=float(epi_cfg.get("finalize_max_age_s", 1800.0)),
    )

    # 4-5. Prompt Assembler 구성 (순수 정적 SystemMessage + 세션 동결 User Context + 스킬 Delta)
    #    - 스킬: 에이전트 내장 skills/ 만 스캔 (Mission 04 금융 스킬도 이 폴더에 설치)
    #    - skills/SKILL.md(스킬 실행 지침)와 초기 스킬 목록은 User Context(# skillCatalog)에 통합, 변경분은 Delta로 주입
    skill_guidelines = str(SKILLS_DIR / "SKILL.md") if (SKILLS_DIR / "SKILL.md").exists() else None
    skill_builder = SkillPromptBuilder(
        skills_dirs=[str(SKILLS_DIR)],
        guidelines_path=skill_guidelines,
    )

    assembler = PromptAssembler(
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        skill_guidelines=skill_builder.load_guidelines,
        skill_provider=skill_builder.list_skills,
    )
    prompt_mw = create_prompt_assembler_middleware(assembler)

    # ─────────────────────────────────────────────────────────────────
    # 5. 통합 미들웨어 파이프라인 (보안 & 거버넌스 순서)
    #
    # 미들웨어는 리스트 순서대로 요청을 감싸는 러시안 인형 구조입니다.
    # 리스트 앞쪽 = 바깥 껍데기(먼저 실행), 뒤쪽 = LLM에 가까운 내부.
    #
    #   요청 → [Log] → [Guard] → [Memory] → [Compaction] → [Prompt] → [HITL] → [SelfRecovery] → [StopHooks] → LLM
    # ─────────────────────────────────────────────────────────────────
    middleware = []

    # (1) Logging & Observability — 전체 실행 흐름 JSONL 감사 로깅
    #     log_dir 미지정(기본): artifacts/users/{user_id}/sessions/{session_id}/logs/audit.jsonl
    #     log_dir 지정 시     : {log_dir}/{session_id}/audit.jsonl
    logging_cfg = _load_config("./configs/logging.config", {"logging_enabled": False})
    if logging_cfg.get("logging_enabled"):
        log_dir = logging_cfg.get("log_dir")
        middleware.append(AgentLogTracer(log_dir=log_dir) if log_dir else AgentLogTracer())

    # (2) Guardrails — 프롬프트 인젝션 차단
    #     fail_mode: 가드레일 LLM 장애 시 "open"(통과) / "close"(차단) — guardrail.config에서 지정
    guardrail_cfg = _load_config("./configs/guardrail.config", {"guardrail_enabled": False})
    if guardrail_cfg.get("guardrail_enabled"):
        guard_model = model_cfg.get("model_name", "gemini-3.8-flash")
        safety_cfg = guardrail_cfg.get("input_safety", {})
        if safety_cfg.get("enabled", True):
            middleware.append(InputSafetyGuardrail(
                model=guard_model,
                fail_mode=safety_cfg.get("fail_mode", "open"),
            ))

    # (3) Memory — 원문 기록·메모리 인출(before_agent, 가드레일 통과 후 실행) + 도구 필터링
    middleware.append(memory_mw)

    # (3-1) Context Compaction (configs/compaction.config)
    #       - 대형 도구 결과 → 디스크 Swap (swap_dir 미지정: artifacts/users/{user_id}/sessions/{session_id}/tool-results/)
    #       - 대화가 trigger_tokens를 넘으면 이전 대화를 요약 (PromptAssembler 앞에 두어 압축 후 skill_delta 재주입)
    #         trigger는 시스템 프롬프트·도구 스키마를 포함한 실사용량과도 비교됩니다.
    #         이 에이전트의 고정 오버헤드가 약 11K 토큰이므로 trigger는 그보다 넉넉히 크게 둡니다.
    compaction_cfg = _load_config("./configs/compaction.config", {"compaction_enabled": False})
    if compaction_cfg.get("compaction_enabled"):
        swap_cfg = compaction_cfg.get("tool_result_swap", {})
        summ_cfg = compaction_cfg.get("summarization", {})
        middleware.extend(create_compaction_middleware(
            llm,
            trigger_tokens=summ_cfg.get("trigger_tokens", 24_000),
            keep_tokens=summ_cfg.get("keep_tokens", 6_000),
            swap_dir=swap_cfg.get("swap_dir"),
            max_result_chars=swap_cfg.get("max_result_chars", 10_000),
            preview_chars=swap_cfg.get("preview_chars", 2_000),
            # 원문 기록이 꺼져 있으면 압축 이벤트도 transcript.db에 남기지 않음
            transcript_store=transcript_store if tr_cfg.get("enabled", True) else None,
        ))

    # (3-2) Prompt Assembler — 정적 SystemMessage + 세션 동결 User Context + Delta 알림 조립
    middleware.append(prompt_mw)

    # (4) Human-in-the-Loop — 지정 도구(roll_dice) 실행 전 사용자 승인 게이트
    hitl_cfg = _load_config("./configs/hitl.config", {"hitl_enabled": False})
    if hitl_cfg.get("hitl_enabled"):
        interrupt_on = hitl_cfg.get("interrupt_on", {})
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # (5) Self-Recovery & Self-Correction Circuit Breakers — 모델/도구 장애 복구 및 코드 검증
    backup_model = os.getenv("FALLBACK_MODEL_NAME", "gpt-6.1-sol")
    middleware.extend([
        ModelFallbackMiddleware(
            max_retries=2,
            initial_delay=0.5,
            fallback_model_name=backup_model
        ),
        ToolErrorHandlerMiddleware(max_retries=0),
        ModelCallLimitMiddleware(run_limit=50, exit_behavior="end"),
        StopHooksMiddleware(),
    ])

    # 6. 하네스로 결합된 최종 메인 에이전트 인스턴스 구축
    return create_agent(
        model=llm,
        tools=active_tools,
        middleware=middleware,
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )

