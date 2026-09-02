# 🛡️ Agent Harness Lab (프로덕션 에이전트 하네스 엔지니어링)

> **LLM 모델을 신뢰할 수 있는 엔터프라이즈 에이전트로 도약시키는 하네스 엔지니어링 종합 실습 파이프라인**  
> 자가 치유(Self-Recovery)부터 2단계 계층형 메모리, Claude Code 표준 5-Layer 프롬프트 조립, Progressive Skills 자율 실행, Human-in-the-Loop 권한 게이트, 가드레일 거버넌스 및 비동기 감사 궤적 관측성까지 — 실전 프로덕션 AI 에이전트 아키텍처를 직접 구축하고 검증합니다.

---

## 📢 v2.0 아키텍처 전면 개편 안내

최신 프로덕션 AI 에이전트 하네스 표준과 생태계에 맞춰 코드베이스를 전면 재설계했습니다.

| 구분 | v1.0 (Legacy) | v2.0 (Current) |
| :--- | :--- | :--- |
| **웹 UI 프론트엔드** | Streamlit (`app/ui.py`) | **Chainlit (`app/chainlit_ui.py`, 포트 `8080`, SSE 스트리밍 & HITL 버튼 연동)** |
| **프롬프트 아키텍처** | 단일 문자열 템플릿 | **Claude Code 표준 5-Layer Prompt Assembler (JIT Dynamic Assembly)** |
| **메모리 시스템** | 단순 대화 체크포인터 | **2-Stage JIT 계층형 메모리 (Semantic Memory + Daemon Background Episodic Store)** |
| **도구 확장 메커니즘** | 정적 함수 바인딩 | **Progressive Skills (Frontmatter 경량 인덱싱 & 토큰 90% 절약형 동적 실행)** |
| **권한 및 보안 제어** | 없음 (완전자율) | **Human-in-the-Loop (`__interrupt__` 기반 권한 게이트 & 웹 승인/거부 인터랙션)** |
| **안전 거버넌스** | 없음 | **Llama Guard 3 S1~S5 입력 보안 필터 & NeMo 규정 일치 리디렉션 가드레일** |
| **관측성 및 로깅** | 단순 콘솔 출력 | **`AgentLogTracer` 비동기 큐 기반 감사 궤적 적재 & `log_analyzer` 통계 대시보드** |
| **런타임 프레임워크** | LangChain 구버전 | **LangChain 1.3+ / LangGraph 1.2+ / Python 3.12 (WSL2 및 Codespaces 최적화)** |

---

## 🚀 시작하기 (환경 세팅)

### 1. GitHub Codespaces 환경 (권장)
GitHub Codespaces 환경에서는 사전 빌드된 Docker 컨테이너를 기반으로 구동되므로, **별도의 패키지 설치 없이 즉시 실행**할 수 있습니다.
1. 리포지토리 상단의 **[Code] ➔ [Codespaces] ➔ [Create codespace on main]**을 클릭합니다.
2. 컨테이너가 열리면 프로젝트 루트의 `.env` 파일을 확인하고 API 키를 입력합니다.

### 2. 로컬 환경 (WSL2 / Linux 수동 설치)
로컬 우분투 또는 WSL2 환경에서 직접 실행할 경우 자동 설치 스크립트를 사용하세요:

```bash
# install 폴더로 이동하여 패키지 설치
cd install
bash install_all.sh
```

### 🔑 환경 변수 설정 (`.env`)
프로젝트 루트에 생성된 `.env` 파일에 사용할 API 키를 설정합니다:

```env
GOOGLE_API_KEY="your-gemini-api-key"
OPENAI_API_KEY="your-openai-api-key"
```

### 📊 LangSmith 트레이싱 및 관측성 설정 (선택 사항)
LangSmith를 통한 실시간 호출 궤적 시각화가 필요한 경우 아래 환경 변수를 추가합니다:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY="your-langsmith-key"
LANGCHAIN_PROJECT=harness_agent
```

---

## 🧭 2단계 커리큘럼: 노트북(개념) ➔ 미션(프로덕션 구현)

학습 흐름은 **노트북(핸즈온 이론 학습)** 후 **미션(프로덕션 에이전트 점진적 빌드업)**을 수행하는 체계적인 2단계 구조입니다.

### 📗 핸즈온 실습 노트북 (이론 & 프로토타이핑)

```text
notebooks/
├── 0_Template.ipynb                       # 📝 하네스 기본 템플릿
├── 1.Reasoning and Subagent.ipynb         # 🤖 ReAct, Task Planning, 서브에이전트 오케스트레이션
├── 2.Prompt_and_Memory.ipynb              # 🧠 5-Layer 프롬프트 조립 & 2-Stage JIT 계층형 메모리
├── 3.Context_Compaction.ipynb             # 📦 컨텍스트 압축, 요약 및 장기 대화 윈도우 보존
├── 4.Skills_and_MCP.ipynb                 # 🧰 Progressive Skills 동적 발견 & Model Context Protocol
├── 5.Evaluation_and_LLM_as_Judge.ipynb    # ⚖️ LLM-as-a-Judge 정량 채점 & 회귀 테스트 자동화
├── 6.Human_in_the_Loop.ipynb              # 🛑 도구 보안 등급제 & LangGraph __interrupt__ 권한 게이트
└── 7.Guardrails_and_Monitoring.ipynb      # 🛡️ Llama Guard 3 입력 보안, NeMo 주제 일치, AgentLogTracer
```

---

### 🎯 실전 프로덕션 미션 로드맵 (단계별 코드베이스 완성)

```text
missions/
├── 00_mission_start_and_chat.md            # 🚀 FastAPI 서버 & Chainlit 웹 UI 구동 및 첫 대화
├── 01_mission_add_custom_tool.md           # 🛠️ 커스텀 도구(주사위/환율) 구현 및 챗봇 바인딩
├── 02_mission_self_recovery_and_subagent.md# 🛡️ 3대 자가 복구 미들웨어 & 서브에이전트 오케스트레이션
├── 03_mission_prompt_and_memory.md         # 🧠 Claude Code 프롬프트 조립기 & 백그라운드 에피소딕 메모리
├── 04_mission_skills.md                    # 🧰 금융 분석 전문 스킬(13종) 동적 카탈로그 주입 & 대시보드
├── 05_mission_human_in_the_loop.md         # 🛑 roll_dice 타깃 HITL 권한 게이트 & 웹 대화형 승인/거절
├── 06_mission_guardrails.md                # 🛡️ 프롬프트 인젝션(S4) 선제 차단 & 오프토픽 대체 안내
└── 07_mission_logging_and_observability.md # 📊 비동기 감사 궤적 적재 & 세션 데이터 분석 대시보드
```

---

## 🖥️ 실시간 백엔드 API & 웹 채팅 UI 가동

노트북 학습 후 완성된 하네스 에이전트 시스템을 실제 서비스 환경으로 실행합니다. **터미널 2개**를 열어 서버와 웹 프론트엔드를 구동하세요.

### 1. 백엔드 서버 (FastAPI) 가동 — 터미널 ①
```bash
python app/server.py --port 8000
```
* 에이전트 서빙 API가 `:8000` 포트에서 가동됩니다.
* `http://localhost:8000/docs`에서 Swagger UI로 API 스펙을 확인할 수 있습니다.

### 2. Chainlit 웹 채팅 UI 가동 — 터미널 ②
```bash
chainlit run app/chainlit_ui.py --port 8080
```
* 브라우저에서 `http://localhost:8080`에 접속하여 실시간 SSE 스트리밍과 도구 실행 과정을 시각적으로 확인합니다.
* **웹 UI 기본 로그인 계정**: ID `user` / PW `1234`
* **HITL 대화형 버튼**, **HTML 대시보드 인라인 렌더링**, **스마트 세션 기억 회상**을 웹에서 즉시 체험할 수 있습니다.

### 3. 터미널 대화형 CLI 클라이언트 (선택)
```bash
python app/client.py
```

### 4. 세션 감사 로그 분석기 실행
대화를 나눈 후 누적된 세션 실행 통계(세션수, 레이턴시, 도구 빈도 TOP 5)를 분석합니다:
```bash
python -m app.utils.log_analyzer
```

---

## 🧪 미션별 자동화 검증 스위트 (Test Suites)

각 미션을 수행한 후 터미널에서 1:1 매핑된 테스트 스크립트를 실행하여 구현의 무결성을 즉시 검증할 수 있습니다:

| 테스트 파일 | 대응 미션 | 주요 검증 내용 | 실행 명령어 |
| :--- | :--- | :--- | :--- |
| **`test_mission01.py`** | Mission 01 | 커스텀 도구 2종 및 `chatbot.py` 바인딩 검증 | `python tests/test_mission01.py` |
| **`test_mission02.py`** | Mission 02 | `main_agent.py` 자가 복구 미들웨어 3종 & 도구 15종 결합 | `python tests/test_mission02.py` |
| **`test_mission03.py`** | Mission 03 | 5-Layer 프롬프트 조립 & 메모리 + **실물 시각화** | `python tests/test_mission03.py` |
| **`test_mission04.py`** | Mission 04 | `skills/` 동적 확장 & Layer 2.2 자동 주입 + **실물 시각화** | `python tests/test_mission04.py` |
| **`test_mission05.py`** | Mission 05 | HITL (`roll_dice` 타깃 권한 게이트 & 승인/거부 재개) | `python tests/test_mission05.py` |
| **`test_mission06.py`** | Mission 06 | Guardrails (입력 보안 필터 차단 & 주제 일치 리디렉션) | `python tests/test_mission06.py` |
| **`test_mission07.py`** | Mission 07 | Logging (`AgentLogTracer` 비동기 적재 & `log_analyzer` 분석) | `python tests/test_mission07.py` |

---

## 📂 프로젝트 구조 (Monorepo)

```text
harness_agent/
├── notebooks/              # 📗 단계별 핸즈온 실습 노트북 (0~7)
├── missions/               # 🎯 단계별 프로덕션 미션 가이드 (00~07)
├── tests/                  # 🧪 미션별 1:1 매핑 자동화 검증 스크립트
├── configs/                # ⚙️ 런타임 하네스 설정 파일 모음
│   ├── model.config        #   └── 메인/가드레일 LLM 모델 지정
│   ├── memory.config       #   └── 세션 메모리 활성화 설정
│   ├── hitl.config         #   └── roll_dice 타깃 HITL 권한 게이트 설정
│   ├── guardrail.config    #   └── 입력 보안 및 주제 차단 목록 설정
│   └── logging.config      #   └── 비동기 감사 로그 적재 경로 설정
├── app/                    # 🧠 프로덕션 에이전트 시스템 코어
│   ├── agents/             #   ├── 에이전트 정의 (chatbot, main_agent, memory_agent 등)
│   ├── tools/              #   ├── 내장 도구 및 커스텀 도구 모음 (custom_tools 등)
│   ├── prompts/            #   ├── 시스템 프롬프트 및 지침서 (SUPERVISOR, SKILL.md 등)
│   ├── middleware/         #   ├── 하네스 미들웨어 모음
│   │   ├── memory/         #   │   └── 시맨틱/에피소딕 계층형 메모리 미들웨어
│   │   ├── prompt/         #   │   └── Claude Code 5-Layer 프롬프트 조립기
│   │   ├── error_control/  #   │   └── 모델 폴백 / 서킷 브레이커 자가 복구 미들웨어
│   │   ├── guardrails/     #   │   └── InputSafetyGuardrail & TopicAlignmentGuardrail
│   │   └── observability/  #   │   └── AgentLogTracer 비동기 감사 로거 및 시각화기
│   ├── utils/              #   ├── 모델 팩토리, 메시지 유틸, log_analyzer 유틸
│   ├── server.py           #   ├── FastAPI 에이전트 API 서빙 서버 (SSE 스트리밍)
│   ├── chainlit_ui.py      #   ├── Chainlit 웹 인터랙티브 채팅 프론트엔드
│   └── client.py           #   └── 터미널 대화형 CLI 클라이언트
├── skills/                 # 🧰 Progressive Skills 패키지 모음 (금융 분석 등 13종)
├── artifacts/              # 📂 메모리 DB, 스킬 풀, 감사 로그 및 파일 적재소
├── install/                # 🚀 자동 설치 스크립트 (requirements.txt 포함)
└── README.md               # 📖 메인 프로젝트 설명서
```

---

## 📚 참고 자료 및 공식 생태계

- [LangChain 공식 문서](https://python.langchain.com)
- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph)
- [Chainlit 공식 문서](https://docs.chainlit.io)
- [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [LangSmith](https://smith.langchain.com)
