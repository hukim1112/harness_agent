# 🎯 Mission 07: Logging & Observability (감사 궤적 & 세션 데이터 분석)

본 미션은 `7.Guardrails_and_Monitoring.ipynb`에서 학습한 **통합 관측성(Observability) 및 비동기 감사 로깅(Audit Logging)** 원리를 바탕으로, 에이전트와 도구의 전체 라이프사이클(사용자 질의, 도구 인자, 반환값, 레이턴시, 토큰 사용량)을 백그라운드에서 실시간 영속화하고, **누적된 세션 감사 로그 데이터를 분석하여 운영 통계 대시보드를 시각화**하는 프로덕션 운영 실습 과제입니다.

---

## 💡 왜 비동기 감사 로깅(`AgentLogTracer`)인가?

1. **에이전트 추론 지연(Latency) 0ms 보장**:
   - 도구나 LLM이 실행될 때마다 디스크에 동기식으로 파일을 쓰면 I/O 병목으로 인해 챗봇 응답이 현저히 느려집니다.
   - `AgentLogTracer`는 내부의 `_AsyncLogWorker` 데몬 스레드와 `queue.Queue`를 통해 **로그 적재 작업을 백그라운드에서 비동기로 처리**하여 사용자 응답 속도를 100% 보존합니다.
2. **세션별 완결된 궤적 추적**:
   - 세션 ID(`thread_id`), 사용자 입력, 에이전트 최종 답변, 격발된 도구 목록 및 실행 시간(ms)이 단일 감사 레코드에 완전하게 기록됩니다.
3. **데이터 기반 운영 최적화**:
   - 누적된 로그를 분석하여 *"어떤 도구가 가장 자주 쓰이는가?"*, *"어떤 도구의 실행 지연(Latency)이 심한가?"*를 객관적 수치로 모니터링할 수 있습니다.

---

## 📂 실습 대상 파일

* **로깅 설정 파일**: [`configs/logging.config`](configs/logging.config)  
  👉 감사 로깅 활성화 여부(`logging_enabled`)와, 필요 시 커스텀 로그 디렉토리(`log_dir`, 선택)를 제어합니다.
* **관측성 미들웨어**: [`app/middleware/observability/agent_log_tracer.py`](app/middleware/observability/agent_log_tracer.py)  
  👉 비동기 큐 기반의 감사 궤적 수집 엔진입니다.
* **에이전트 결합 파일**: [`app/agents/main_agent/agent.py`](app/agents/main_agent/agent.py)  
  👉 `logging.config`에 따라 `AgentLogTracer`를 미들웨어 파이프라인의 최우선 순위로 마운트합니다.
* **세션 로그 분석기**: [`app/utils/log_analyzer.py`](app/utils/log_analyzer.py)  
  👉 적재된 JSONL 로그를 파싱하여 통계 대시보드를 출력하는 유틸리티입니다.
* **자동화 검증 스크립트**: [`tests/test_mission07.py`](tests/test_mission07.py)

---

## 🛠️ 단계별 수행 가이드

### 1단계: `configs/logging.config` 활성화하기

[`configs/logging.config`](configs/logging.config) 파일을 열고 `"logging_enabled": true`로 변경합니다:

```json
{
  "logging_enabled": true
}
```

| 설정 | 로그 저장 위치 |
| :--- | :--- |
| `log_dir` 미지정 (기본, 권장) | `artifacts/users/{user_id}/sessions/{session_id}/logs/audit.jsonl` (서브에이전트는 `.../subagents/{role}_{id}/logs/audit.jsonl`) |
| `"log_dir": "./my_logs"` 지정 | `./my_logs/{session_id}/audit.jsonl` |

---

### 2단계: `app/agents/main_agent/agent.py`에 `AgentLogTracer` 직접 장착하기

`app/agents/main_agent/agent.py`를 열고, `configs/logging.config`가 활성화(`logging_enabled: true`)되었을 때 `AgentLogTracer`를 미들웨어 파이프라인의 **가장 앞단(1순위)**에 마운트합니다.

> 📌 **미들웨어 파이프라인 위치 안내** (상세 순서: [`MIDDLEWARE_PIPELINE_REFERENCE.md`](./MIDDLEWARE_PIPELINE_REFERENCE.md) 참고):  
> 감사 로깅(`AgentLogTracer`)은 **가드레일에 의해 차단된 요청까지 포함하여 에이전트의 전체 라이프사이클을 빠짐없이 기록**해야 하므로, 반드시 `middleware = []` 직후인 **가장 바깥쪽(`(1) Logging` 위치, `(2) Guardrails` 앞)**에 배치합니다!

1. 파일 상단에 `AgentLogTracer` 임포트를 추가합니다:
   ```python
   from app.middleware.observability import AgentLogTracer
   ```

2. `create_agent_executor()` 내부의 `middleware = []` 바로 아래(가장 앞단)에 **`(1) Logging & Observability`** 블록을 추가합니다:
   ```python
   middleware = []

   # (1) Logging & Observability — 전체 실행 흐름 JSONL 감사 로깅 (가장 바깥에 위치!)
   logging_cfg = _load_config("./configs/logging.config", {"logging_enabled": False})
   if logging_cfg.get("logging_enabled"):
       log_dir = logging_cfg.get("log_dir")
       middleware.append(AgentLogTracer(log_dir=log_dir) if log_dir else AgentLogTracer())

   # (2) Guardrails ...
   ```

<details>
<summary><b>👉 최종 완성된 <code>app/agents/main_agent/agent.py</code> 전체 코드 (Mission 07 완료 시점)</b></summary>

```python
import os
import json
from pathlib import Path
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware

from app.utils import init_chat_model
from app.context import AgentContext
from .prompt import SUPERVISOR_SYSTEM_PROMPT
from .tools import tools_supervisor
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

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

AGENT_METADATA = {
    "name": "main_agent",
    "description": "하네스 기능을 연결할 메인 오케스트레이터 에이전트",
    "roles": ["main"],
}


def _load_config(path: str, default: dict) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


async def create_agent_executor(checkpointer=None):
    model_cfg = _load_config("./configs/model.config", {
        "model_name": "gemini-3.8-flash",
        "temperature": 0.0,
    })
    llm = init_chat_model(
        model=model_cfg.get("model_name", "gemini-3.8-flash"),
        temperature=model_cfg.get("temperature", 0.0)
    )

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

    memory_cfg = _load_config("./configs/memory.config", {})
    sem_cfg = memory_cfg.get("semantic_memory", {})
    epi_cfg = memory_cfg.get("episodic_memory", {})

    memory_dir = sem_cfg.get("memory_dir", "./artifacts/users/default/memory")
    os.makedirs(memory_dir, exist_ok=True)
    semantic_store = SemanticMemoryStore(
        memory_dir=memory_dir,
        memory_char_limit=4000,
        user_char_limit=2000,
    )
    semantic_store.load_from_disk()

    episodic_db_path = epi_cfg.get("db_path", os.path.join(db_dir, "episodic.db"))
    os.makedirs(os.path.dirname(episodic_db_path) or ".", exist_ok=True)
    episodic_store = EpisodicStore(db_path=episodic_db_path)
    await episodic_store.setup()

    memory_mw = MemoryMiddleware(
        semantic_store=semantic_store,
        episodic_store=episodic_store,
        review_llm=llm,
        top_k=epi_cfg.get("top_k_prefetch", 2),
    )
    active_tools = list(tools_supervisor) + [roll_dice, convert_currency]

    skill_guidelines = str(SKILLS_DIR / "SKILL.md") if (SKILLS_DIR / "SKILL.md").exists() else None
    skill_builder = SkillPromptBuilder(
        skills_dirs=[str(SKILLS_DIR)],
        guidelines_path=skill_guidelines,
    )

    assembler = PromptAssembler(
        system_rules=SUPERVISOR_SYSTEM_PROMPT,
        tool_schemas=active_tools,
        skill_catalog=skill_builder.assemble,
        l4_docs={},
    )
    prompt_mw = create_prompt_assembler_middleware(assembler, merge_system=True)

    middleware = []

    # (1) Logging & Observability
    logging_cfg = _load_config("./configs/logging.config", {"logging_enabled": False})
    if logging_cfg.get("logging_enabled"):
        log_dir = logging_cfg.get("log_dir")
        middleware.append(AgentLogTracer(log_dir=log_dir) if log_dir else AgentLogTracer())

    # (2) Guardrails
    guardrail_cfg = _load_config("./configs/guardrail.config", {"guardrail_enabled": False})
    if guardrail_cfg.get("guardrail_enabled"):
        guard_model = model_cfg.get("model_name", "gemini-3.8-flash")
        safety_cfg = guardrail_cfg.get("input_safety", {})
        if safety_cfg.get("enabled", True):
            middleware.append(InputSafetyGuardrail(
                model=guard_model,
                fail_mode=safety_cfg.get("fail_mode", "open"),
            ))
        topic_cfg = guardrail_cfg.get("topic_alignment", {})
        if topic_cfg.get("enabled", True):
            middleware.append(TopicAlignmentGuardrail(
                model=guard_model,
                allowed_topics=topic_cfg.get("allowed_topics"),
                blocked_topics=topic_cfg.get("blocked_topics"),
                fail_mode=topic_cfg.get("fail_mode", "open"),
            ))

    # (3) Memory & Prompt
    middleware.extend([memory_mw, prompt_mw])

    # (4) Human-in-the-Loop
    hitl_cfg = _load_config("./configs/hitl.config", {"hitl_enabled": False})
    if hitl_cfg.get("hitl_enabled"):
        interrupt_on = hitl_cfg.get("interrupt_on", {})
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    # (5) Self-Recovery
    backup_model = os.getenv("FALLBACK_MODEL_NAME", "gpt-6.1-sol")
    middleware.extend([
        ModelFallbackMiddleware(
            max_retries=2,
            initial_delay=0.5,
            fallback_model_name=backup_model
        ),
        ToolErrorHandlerMiddleware(max_retries=0),
        ModelCallLimitMiddleware(run_limit=50, exit_behavior="end"),
    ])

    main_agent = create_agent(
        model=llm,
        tools=active_tools,
        middleware=middleware,
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )

    main_agent.registered_tools = active_tools
    main_agent.registered_middlewares = middleware
    main_agent.checkpointer_conn = conn
    main_agent.episodic_store = episodic_store
    main_agent.semantic_store = semantic_store
    main_agent.assembler = assembler
    main_agent.memory_middleware = memory_mw

    return main_agent
```
</details>

---

### 3단계: 자동화 검증 스크립트 실행

터미널에서 감사 궤적 적재 및 분석기 동작을 검증합니다:

```bash
python tests/test_mission07.py
```

#### ✅ 기대 성공 출력:
```text
======================================================================
🧪 [Mission 07] Logging & Observability (감사 궤적 & 세션 분석) 검증 시작
======================================================================
  ✅ Test 1 통과: configs/logging.config 규격 및 main_agent AgentLogTracer 장착 확인 완료
  ✅ Test 2 통과: 비동기 감사 궤적 적재 확인 (총 3개 레코드 생성)
  ✅ Test 3 통과: log_analyzer 메트릭 및 통계 집계 검증 완료

======================================================================
📊 [Agent Observability] 세션 감사 로그 분석 대시보드
======================================================================
  • 분석 대상 로그 파일  : 1 개
  • 고유 세션 수 (Sessions): 2 개
  • 총 에이전트 실행 횟수: 2 회
  • 총 도구(Tool) 격발 수: 1 회
  • 평균 에이전트 레이턴시: 4137.0 ms
  • 평균 도구 실행 시간  : 1.0 ms

[🛠️ 도구별 사용 빈도 및 평균 레이턴시 TOP 5]
----------------------------------------------------------------------
  순위   | 도구 이름                      | 호출 횟수      | 평균 레이턴시
----------------------------------------------------------------------
  #1   | roll_dice                  | 1          | 1.0 ms
======================================================================

🎉 [Mission 07] Logging & Observability (감사 궤적 & 세션 분석) 100% 통과!
```

---

### 4단계: Chainlit UI 실시간 대화 후 세션 로그 데이터 분석하기

1. 터미널 2개를 열어 서버와 Chainlit UI를 띄웁니다:
   ```bash
   python app/server.py --port 8000
   chainlit run app/chainlit_ui.py --port 8080
   ```
2. 웹 브라우저(`http://localhost:8080`)에서 `main_agent`와 2~3턴 대화를 나눕니다:
   - *"삼성전자 최신 주가 추세 알려줘"* (스킬 및 도구 격발)
   - *"주사위 3개 굴려줘"* (커스텀 도구 격발)
3. 새 터미널 창에서 **세션 로그 분석기**를 실행합니다:
   ```bash
   python -m app.utils.log_analyzer
   ```
4. **결과 확인**:
   - 방금 나눈 대화 세션의 총 수, 평균 응답 시간, 사용된 도구(`pykrx-korean-market`, `roll_dice` 등)의 호출 빈도와 평균 실행 시간이 표로 깔끔하게 정리되어 출력되는 것을 확인합니다!

---

## 🏆 Mission 07 완료 체크리스트

- [ ] 비동기 감사 로깅(`_AsyncLogWorker`)을 통한 0ms 레이턴시 보존 원리를 이해했다.
- [ ] `configs/logging.config`에서 `logging_enabled: true`로 활성화했다.
- [ ] `app/agents/main_agent/agent.py`의 미들웨어 파이프라인 최상단(1순위)에 `AgentLogTracer`를 마운트했다.
- [ ] `python tests/test_mission07.py`를 실행하여 단위 테스트를 100% 통과했다.
- [ ] Chainlit UI 대화 후 `python -m app.utils.log_analyzer`를 실행하여 실시간 세션 감사 통계 대시보드를 확인했다.
