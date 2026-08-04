# 🛡️ Agent Harness Lab (하네스 엔지니어링 실습 파이프라인)

본 프로젝트는 **"하네스 엔지니어링 기반 에이전트 개발"** 교육을 위한 종합 실습 코드베이스입니다.

---

## 🚀 시작하기 (환경 세팅)

Codespaces 또는 로컬 WSL2(우분투) 환경을 처음 열었다면, 터미널에서 다음 명령어를 실행하여 가상환경 세팅 및 의존성 패키지를 한 번에 설치하세요.

```bash
# 1. install 폴더로 이동하여 자동 설치 스크립트 실행
cd install
bash install_all.sh
```

설치가 완료되면 Python 패키지 의존성 설치 및 `.env` 템플릿 복사 작업이 자동으로 완료됩니다.

### 환경 변수 설정
프로젝트 루트에 생성된 `.env` 파일을 메모장이나 주피터에서 열고 사용할 API 키를 설정하세요.

```env
OPENAI_API_KEY="your-openai-api-key"
GOOGLE_API_KEY="your-gemini-api-key"
```

### 📊 LangSmith 트레이싱 및 관측성 설정 (권장)
에이전트 실행 흐름의 레이턴시와 호출 과정을 시각적으로 감사하기 위해 LangSmith 키를 추가 설정합니다.

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY="your-langsmith-key"
LANGCHAIN_PROJECT=agent-harness-lab
```

---

## 🧭 커리큘럼 및 노트북 구조

학습 흐름은 점진적 빌드업(Step-by-step) 형태로 구성되어 있습니다.

```text
notebooks/
├── 01_reasoning_and_multiagent.ipynb   # [추론] Naive, Planner(CoT, Task, Explicit), 협업 프로토콜
├── 02_context_management.ipynb         # [컨텍스트] KV Caching 최적화, Hermes 4계층 메모리
├── 03_tool_and_mcp.ipynb               # [도구/MCP] Progressive Disclosure, ACI 스키마, SQLite MCP
├── 04_human_in_the_loop.ipynb          # [권한/HITL] 3단계 권한 제어 게이트 (Allow/Deny/Edit)
└── 05_guardrails_and_monitoring.ipynb  # [안전/로깅] 3대 가드레일 에뮬레이션, 관측성 미들웨어 로깅
```

| 단계 | 노트북 | 핵심 학습 목표 |
|:---:|--------|-----------|
| **1** | `01_reasoning_and_multiagent` | CoT/Task/Explicit Planner 아키텍처 및 멀티에이전트 협업 프로토콜 비교 실습 |
| **2** | `02_context_management` | 프롬프트 캐싱 최적화 및 4계층 장기/단기 에이전트 메모리 설계 |
| **3** | `03_tool_and_mcp` | 스킬 자율 발견(Progressive Disclosure) 및 Model Context Protocol(MCP) 데이터 연동 |
| **4** | `04_human_in_the_loop` | CLI/UI 환경에서의 인간 개입(HITL) 및 3단계 권한 모델 구현 |
| **5** | `05_guardrails_and_monitoring` | 가드레일 및 로깅 미들웨어 감사 로그 적재 |

---

## 🖥️ 실시간 백엔드 API & 채팅 UI 가동

노트북 실습이 완료되면, 에이전트들을 서비스용 백엔드 API와 실시간 채팅 웹 인터페이스 형태로 구동할 수 있습니다. 

```
[사용자 (Streamlit UI)] ──(HTTP/SSE)──> [FastAPI 백엔드 Server] ──> [Harness 에이전트]
```

### 1. 백엔드 서버(FastAPI) 가동
에이전트를 호스팅하는 API 엔드포인트를 구동합니다.
```bash
python app/server.py --port 8000
```
* 서버 실행 후 `http://localhost:8000/docs` 에서 Swagger 문서 형태로 에이전트 작동 상태를 테스트할 수 있습니다.

### 2. Streamlit 웹 채팅 UI 가동
사용자 친화적인 인터랙티브 채팅 화면을 띄워 에이전트들을 제어합니다.
```bash
streamlit run app/ui.py
```
* 브라우저에서 `http://localhost:8501`에 접속한 뒤 사이드바에서 작동시킬 에이전트 모델을 스위칭하고 대화를 나누어 보세요.

---

## 📂 프로젝트 구조

```text
agent-harness-lab/
├── notebooks/              # 📗 단계별 핸즈온 실습 노트북 (01~05)
├── src/                    # ⚙️ 모듈화된 프로덕션 파이썬 패키지
│   └── harness/            #   └── 하네스 코어 모듈 (reasoning, context, tools, monitoring 등)
├── app/                    # 🧠 서빙 및 인터페이스 애플리케이션
│   ├── agents/             #   └── 에이전트 핵심 구동기 (chatbot.py 등)
│   ├── prompts/            #   └── 에이전트 시스템 지침 정의서 (chatbot.py 등)
│   ├── tools/              #   └── 에이전트 격발 도구 정의서 (common.py 등)
│   ├── utils/              #   └── 모델 팩토리 및 메시지 포맷 헬퍼 (llm.py 등)
│   ├── server.py           #   └── 에이전트 서빙 API 서버 (FastAPI)
│   ├── ui.py               #   └── 에이전트 실시간 채팅 웹 UI (Streamlit)
│   └── client.py           #   └── 터미널용 대화형 테스트 CLI 클라이언트
├── skills/                 # 🛠️ 에이전트가 점진적으로 학습할 스킬 폴더
│   ├── mcp/                #   └── SQLite MCP 제어 도구 세트
│   └── pdf_processing/     #   └── 가상/바이너리 PDF 텍스트 및 메타데이터 파서 스킬 세트
├── artifacts/              # 📂 감사 로그 및 파일 적재 산출물
├── install/                # 🚀 자동 설치 스크립트 모음 (requirements.txt 포함)
└── README.md               # 📖 메인 프로젝트 설명서
```
