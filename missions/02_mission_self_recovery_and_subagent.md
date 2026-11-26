# 🎯 Mission 02: 메인 오케스트레이터 구축 — 자가 복구(Self-Recovery) & 서브에이전트(Sub-Agent) 위임

앞서 Mission 00과 01에서 우리는 단일 챗봇의 기본 하네스와 커스텀 도구 연결을 배웠습니다.  
하지만 실제 프로덕션 환경에서는 **LLM 통신 장애, 도구 실행 예외, 무한 루프** 같은 시스템 결함이 빈번하게 발생하며, 단일 에이전트에게 모든 도구를 쥐어주면 **컨텍스트 오염과 정보 불균형(Information Asymmetry)**으로 인해 에이전트가 길을 잃게 됩니다.

본 미션에서는 앞으로 우리 프로젝트의 중심이 될 **`app/agents/main_agent/agent.py` (메인 오케스트레이터)**를 구축합니다.  
에이전트 루프를 보호하는 **자가 복구(Self-Recovery) 미들웨어 3종**과, 전문 서브에이전트에게 작업을 위임하는 **오케스트레이션 도구**를 장착하고 검증합니다.

---

## 📂 실습 대상 파일 안내

| 파일 경로 | 역할 | 실습 내용 |
| :--- | :--- | :--- |
| `app/agents/main_agent/agent.py` | 메인 에이전트 | 하네스 기능을 연결할 메인 오케스트레이터 (Self-Recovery & `tools_supervisor` 바인딩) |
| `tests/test_mission02.py` | 자동화 검증 스크립트 | 미들웨어 및 도구 장착 여부, 스모크 테스트 실행 |

---

## 💡 핵심 이론: 하네스가 에이전트를 보호하는 원리

### 1. Self-Recovery vs Self-Correction
* **Self-Correction (자가 수정)**: 모델 자신의 추론 오류를 프롬프트 재질문이나 비평(Critic)을 통해 **LLM 스스로** 고치는 것.
* **Self-Recovery (자가 복구)**: LLM의 개입 없이, **하네스(Middleware)가 시스템/도구 에러를 가로채어 투명하게 복구**하는 것.

```mermaid
graph LR
    subgraph Agent Loop with Self-Recovery
        A["사용자 요청"] --> M["주 모델 호출"]
        M -->|503/429 장애| F["ModelFallbackMiddleware<br/>(백업 모델로 투명 전환)"]
        F --> T["도구(Tool) 실행"]
        T -->|Exception 발생| E["ToolErrorHandlerMiddleware<br/>(에러를 Observation으로 변환)"]
        E -->|무한 루프 감지| L["ModelCallLimitMiddleware<br/>(50회 초과 시 강제 차단)"]
        L --> R["안전한 최종 응답 반환"]
    end
```

* **`ModelFallbackMiddleware`**: 주 모델 API가 일시적으로 먹통이 되면 지수 백오프 재시도 후 백업 모델(`gpt-6.1-sol` — 주 모델과 다른 공급자인 OpenAI)로 자동 failover합니다.
* **`ToolErrorHandlerMiddleware`**: 도구가 `raise Exception`을 일으켜도 전체 서버가 크래시되지 않도록 에러를 `ToolMessage(content='[TOOL_ERROR] ...')` 관찰값으로 변환하여 모델이 대안을 찾을 수 있게 돕습니다.
* **`ModelCallLimitMiddleware`**: 도구가 계속 실패하거나 완료되지 않는 무한 루프 상태에 빠졌을 때 호출 한도(50회)를 적용하여 과금 폭주를 방지합니다.

### 2. Sub-Agent Orchestration (전문 에이전트 위임)
메인 에이전트 혼자서 크롤링, 데이터 분석, 보고서 작성까지 모든 도구를 다 쓰려 하면 컨텍스트가 폭발합니다.  
Supervisor는 계획을 수립하고, **`invoke_sub_agent`** 도구를 통해 `AGENT_METADATA["roles"]`에 `"sub"` 역할이 부여된 전문 에이전트(`scraper`, `analyst`)에게 독립된 세션으로 작업을 위임한 뒤 요약 보고서만 회수합니다. (`main_agent`, `chatbot`처럼 `"roles": ["main"]`만 가진 에이전트는 위임 대상에서 자동 제외됩니다.)

#### 🔄 백그라운드 서브에이전트 실행 및 Reactive Wakeup 흐름 (`run_in_background=True`)
크롤링이나 대시보드 생성처럼 수 분이 걸리는 무거운 작업은 동기식 대기 시 HTTP 타임아웃과 UI 블로킹을 유발합니다. 이를 방지하기 위해 FastAPI 작업 관리자(Job Runner)가 비동기로 백그라운드 작업을 처리하고, **완료 즉시 Supervisor를 자동으로 다시 깨워(Reactive Wakeup) 후속 작업을 마친 뒤 사용자에게 최종 결과를 전달**합니다.

```mermaid
sequenceDiagram
    autonumber
    actor User as 👤 사용자
    participant UI as 💬 Chainlit UI
    participant Sup as 👑 Supervisor (main_agent)
    participant API as 🚀 FastAPI 작업 관리자 (Job Runner)
    participant Sub as 🔬 Sub-Agent (analyst / scraper)

    User->>UI: "엔비디아 소식을 카드뉴스로 시각화해줘"
    UI->>Sup: POST /agents/main_agent/stream
    Sup->>API: invoke_sub_agent(run_in_background=True)<br/>POST /agents/analyst/jobs
    API->>Sub: 독립 세션(sub_thread_id)으로 백그라운드 실행 시작
    activate Sub
    API-->>Sup: Job ID 즉시 반환 (~0.1초)
    Sup-->>UI: "백그라운드 작업을 위임했습니다 (Job ID)" (1차 턴 종료)
    UI-->>User: 작업 시작 안내 (대기 중 다른 질문·대화 가능)

    Note over Sub: 독립 컨텍스트에서 심층 분석 및 HTML 대시보드 생성 수행
    Sub-->>API: [TASK REPORT] 산출물 경로 및 완료 보고 반환
    deactivate Sub

    API->>Sup: 완료 통보 (Reactive Wakeup)<br/>[SYSTEM NOTIFICATION: SUB-AGENT COMPLETED] + [TASK REPORT]
    activate Sup
    Note over Sup: 완료 보고서 검토 및 후속 작업 수행<br/>(결과 종합, 필요 시 추가 위임, Render_HTML 응답 구성)
    Sup-->>API: 최종 응답(supervisor_response) 작성 및 Checkpointer/Job Store 저장
    deactivate Sup

    UI->>API: 세션 모니터링 (GET /sessions/{thread_id}/jobs)
    API-->>UI: 완료 상태 + Supervisor 최종 응답 전달
    UI-->>User: 🔔 백그라운드 작업 완료 알림 + 최종 보고서 및 시각화 결과 전달!
```

- **비블로킹 위임 & 세션 격리**: 위임 즉시 `Job ID`를 받고 1차 턴을 끝내므로 사용자는 기다리지 않고 다른 대화를 이어갈 수 있으며, 서브에이전트는 고유 `sub_thread_id`로 분리되어 단기 기억이 섞이지 않습니다.
- **작업 관리자 → Supervisor 자동 재개(Wakeup)**: 서브에이전트가 종료되면 FastAPI 작업 관리자가 `[TASK REPORT]`를 실어 Supervisor를 자동 호출하므로, 사용자가 *"다 됐어?"* 라고 묻지 않아도 Supervisor가 후속 종합 작업과 시각화 태그 생성을 마친 최종 결과를 전달합니다.

---

## 🛠️ 실습 단계별 수행 가이드

### 1단계: `app/agents/main_agent/agent.py` 열기

`app/agents/main_agent/agent.py` 파일을 열고 구조를 확인합니다. 현재는 `middleware`와 `active_tools`가 빈 리스트(`[]`)로 되어 있는 스타터 상태입니다. 아래 안내에 따라 자가 복구 미들웨어와 오케스트레이션 도구를 단계별로 연결해 보세요.

---

### 2단계: Self-Recovery 미들웨어 3종 임포트 및 등록

1. 파일 상단에서 미들웨어 3종을 임포트합니다:
   ```python
   from app.middleware.error_control.self_recovery import (
       ModelFallbackMiddleware,
       ToolErrorHandlerMiddleware,
       ModelCallLimitMiddleware,
   )
   ```
2. `create_agent_executor` 함수 내부의 **`# 5. 미들웨어 파이프라인`** 구간(`middleware = []` 바로 아래)에 아래 Self-Recovery 블록을 추가합니다:
   ```python
   middleware = []

   # (5) Self-Recovery Circuit Breakers — 모델/도구 장애 자동 복구
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
   ```
   > 💡 이후 Mission 03~07에서 추가되는 미들웨어(로깅, 가드레일, 메모리/프롬프트, HITL)는 이 `middleware = []`와 `# (5) Self-Recovery` 사이에 순서대로 끼워 넣게 되므로, 기존 코드를 지우지 않고 그대로 누적 확장할 수 있습니다.

#### 📊 미들웨어 핵심 파라미터 상세 요약

| 미들웨어 | 주요 파라미터 | 권장 설정값 | 파라미터 역할 및 설정 근거 |
| :--- | :--- | :---: | :--- |
| **`ModelFallbackMiddleware`** | `max_retries` | `2` | 429(Rate Limit), 503 등 일시적 네트워크 장애 시 지수 백오프로 최대 2회 재시도 |
| | `initial_delay` | `0.5` | 첫 번째 재시도 전 대기 시간(0.5초 ➔ 1.0초). 실시간 채팅 UI에서 체감 지연 최소화 |
| | `fallback_model_name` | `gpt-6.1-sol` (`.env`의 `FALLBACK_MODEL_NAME`) | 주 모델 API 마비 시 사용자 몰래 투명하게 전환할 안정적인 백업 모델 |
| **`ToolErrorHandlerMiddleware`** | `max_retries` | `0` | 도구 자체의 무의미한 맹목 재시도를 방지하고, 즉시 에러를 `ToolMessage` 관찰값으로 변환 |
| **`ModelCallLimitMiddleware`** | `run_limit` | `50` | 오케스트레이터의 멀티스텝 작업(계획+태스크생성+서브에이전트호출) 완수를 위한 충분한 턴 한도 (15회는 조기 중단 위험) |
| | `exit_behavior` | `"end"` | 한도 도달 시 예외 크래시 대신 직전 응답으로 루프를 안전 종료 |

> [!NOTE]
> **Q. `ToolErrorHandlerMiddleware`의 `max_retries`는 왜 0인가요?**  
> 도구 실행 실패의 90% 이상은 인자 오류(잘못된 파일 경로, 없는 셀렉터 등)입니다. 인자가 틀렸는데 도구를 똑같이 3번 재시도해 봐야 3번 모두 똑같이 실패하고 시간만 낭비됩니다.  
> 따라서 도구 레벨의 맹목적 재시도는 하지 않고(`max_retries=0`), **에러 내용을 즉시 `ToolMessage` 관찰값(Observation)으로 LLM에 넘겨주어 LLM이 인자를 스스로 수정하거나 대안 경로(Backtracking)를 찾도록 유도**하는 것이 에이전트 하네스의 표준 설계입니다. (생략 시 기본값도 `0`입니다.)

---

### 3단계: Subagent 및 Planning 도구 바인딩

1. 파일 상단에 패키지 내부의 `tools_supervisor`가 임포트되어 있는지 확인합니다:
   ```python
   from .tools import tools_supervisor
   ```
2. **`# 4. 도구 바인딩`** 구간의 `active_tools` 변수에 바인딩합니다:
   ```python
   active_tools = list(tools_supervisor)
   ```
   > 💡 `tools_supervisor`에는 계획 수립 도구 5종(`enter_plan`, `task_create` 등), 서브에이전트 오케스트레이션 도구 4종(`list_sub_agents`, `invoke_sub_agent`, `get_sub_agent_job_status`, `cancel_sub_agent_job`), 공통 범용 도구 8종을 합쳐 **총 17종**이 통합되어 있습니다.

<details>
<summary><b>👉 완성된 <code>app/agents/main_agent/agent.py</code> 전체 코드 (Mission 02 시점 참고용)</b></summary>

```python
import os
import json
from pathlib import Path
from langchain.agents import create_agent

from app.utils import init_chat_model
from app.utils.database import get_shared_checkpointer
from app.context import AgentContext
from .prompt import SUPERVISOR_SYSTEM_PROMPT
from .tools import tools_supervisor
from app.middleware.error_control.self_recovery import (
    ModelFallbackMiddleware,
    ToolErrorHandlerMiddleware,
    ModelCallLimitMiddleware,
)

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

AGENT_METADATA = {
    "name": "main_agent",
    "description": "하네스 기능을 연결할 메인 오케스트레이터 에이전트",
    "roles": ["main"],  # main: UI 대화 전용 (서브에이전트 위임 대상 제외)
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

    if checkpointer is None:
        checkpointer = await get_shared_checkpointer()

    # 4. 도구 바인딩
    active_tools = list(tools_supervisor)

    # 5. 미들웨어 파이프라인
    middleware = []

    # (5) Self-Recovery Circuit Breakers — 모델/도구 장애 자동 복구
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

    return create_agent(
        model=llm,
        tools=active_tools,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )
```
</details>

---

### 4단계: 자동화 검증 스크립트 실행

Codespaces 터미널에서 작성한 코드가 올바르게 조립되었는지 테스트 스크립트로 검증합니다:

```bash
python tests/test_mission02.py
```
> [!NOTE]
> 에이전트 메타데이터, 미들웨어 3종 등록 여부, 도구 목록, 스모크 테스트가 모두 통과하면 `🎉 모든 검증 통과!` 메시지가 출력됩니다.

---

### 5단계: Chainlit UI에서 시나리오 테스트

1. 터미널 ①에서 서버를 재시작합니다:
   ```bash
   python app/server.py --port 8000
   ```
2. Codespaces 포트 탭에서 `8080` 포트로 접속한 뒤, 좌측 상단 프로필에서 **`main_agent`**를 선택합니다.

#### 🧪 시나리오 ①: Planning 기반 엔비디아 최신 소식 조사
* **사용자 입력**:
  ```text
  엔비디아와 관련한 최신 소식들을 조사하고 싶어. 계획을 먼저 수립해줘. 그리고 조사 작업을 수행해줘.
  ```
* **관찰 포인트**:
  - `enter_plan(intent="new", goal=...)`로 계획 모드에 진입한 뒤 `exit_plan(plan_name, steps)`으로 실행 단계를 확정(`plan_state.json`)하고, `task_create` 도구가 호출되어 세션별 상태 칠판(`task_state.json`)에 체계적인 조사 단계(정보 검색 ➔ 주요 이슈 분류 ➔ 요약 보고)를 등록합니다.
  - `web_search` 도구를 스스로 실행하여 최신 엔비디아 실적, 신제품(블랙웰 GPU 등), AI 인프라 동향을 수집하고 단계별로 `task_update(..., "COMPLETED")`를 호출해 모든 과제를 완료한 뒤 브리핑합니다.

#### 🧪 시나리오 ②: 서브에이전트 목록 확인 및 Analyst 카드뉴스 시각화 위임
* **사용자 입력**:
  ```text
  현재 사용 가능한 서브에이전트 목록을 확인해주고, analyst 에이전트에게 '엔비디아 관련한 최신 소식을 바탕으로 카드 뉴스 형식의 자료로 시각화해줘'라고 위임해줘.
  ```
* **관찰 포인트**:
  - `list_sub_agents`가 호출되어 시스템에 등록된 위임 가능 서브에이전트 목록(`scraper`, `analyst`)을 실시간으로 확인합니다.
  - `invoke_sub_agent(subagent_role="analyst", task_instruction="...", run_in_background=True)`가 실행되어 분석 및 시각화 전문 에이전트에게 독립된 서브에이전트 세션(`sub_thread_id`)으로 작업이 위임됩니다.
  - Analyst 서브에이전트가 `html_report` 도구를 호출하여 세션 `outputs/` 폴더에 멋진 반응형 카드뉴스 HTML을 생성하고, 메인 에이전트가 `<Render_HTML>` 태그를 통해 채팅 UI에 즉시 시각화 임베딩하여 보여주는지 확인합니다.

---

## 🏆 Mission 02 완료 체크리스트

- [ ] `app/agents/main_agent/agent.py`에 Self-Recovery 미들웨어 3종(`ModelFallback`, `ToolErrorHandler`, `ModelCallLimit`)이 등록되었다.
- [ ] `app/agents/main_agent/agent.py`에 `tools_supervisor` 도구가 정상 바인딩되었다.
- [ ] `python tests/test_mission02.py` 테스트가 에러 없이 성공했다.
- [ ] Chainlit UI에서 `main_agent`를 선택하고 서브에이전트 위임 및 계획 수립 대화가 정상 동작함을 확인했다.
