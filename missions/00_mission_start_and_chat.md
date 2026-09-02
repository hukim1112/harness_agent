# 🎯 Mission 00: 서버 & Chainlit UI 구동 및 기본 하네스 4대 요소 체감하기

에이전트 하네스 엔지니어링(Harness Engineering)의 첫걸음에 오신 것을 환영합니다!  
하네스(Harness)란 LLM 모델 단독으로는 수행할 수 없는 **상태 관리, 도구 제어, 메모리 영속성, UI 연동**을 안전하고 견고하게 감싸주는 실행 환경(Scaffolding)을 의미합니다.

본 미션에서는 에이전트의 가장 기본이 되는 **최소 기능 하네스(Minimum Viable Harness)**가 탑재된 `chatbot` 에이전트를 가동하고, FastAPI 서버와 Chainlit UI 환경에서 직접 대화를 나누며 하네스의 4대 핵심 요소를 체감합니다.

---

## 📂 실습 대상 파일 안내

| 파일 경로 | 역할 | 실습 중 관찰 및 확인할 내용 |
| :--- | :--- | :--- |
| `app/agents/chatbot.py` | 에이전트 팩토리 | 하네스 4대 기본 요소(프로필, 프롬프트, 도구, 단기기억) 코드 구조 확인 |
| `app/prompts/CHATBOT.py` | 시스템 프롬프트 | 고양이 페르소나 및 응답 제약사항 정의 |
| `app/server.py` | FastAPI 백엔드 서버 | `app/agents/` 디렉토리 자동 스캔 및 SSE 스트리밍 서빙 |
| `app/chainlit_ui.py` | Chainlit 프론트엔드 UI | 서버에서 에이전트 프로필을 동적으로 불러와 렌더링 |

---

## 🧩 에이전트를 지탱하는 기본 하네스 4대 요소

`app/agents/chatbot.py` 파일을 열어보면 에이전트가 다음 4가지 핵심 하네스 요소로 조립되어 있음을 확인할 수 있습니다.

```mermaid
graph TD
    subgraph Agent Harness (chatbot.py)
        A["1. Agent Profile (AGENT_METADATA)"] --> UI["UI 드롭다운 및 설명 표출"]
        B["2. System Prompt (CHATBOT_SYSTEM_PROMPT)"] --> P["고양이 페르소나 & 파일 규칙"]
        C["3. Tools (active_tools)"] --> T["에이전트가 실행 가능한 도구 집합"]
        D["4. Short-term Memory (AsyncSqliteSaver)"] --> M["대화 스레드별 체크포인트 영속 저장"]
    end
    LLM["LLM (Gemini / Claude / GPT)"] --- B
    Harness["Compiled StateGraph"] --> Server["FastAPI :8000"]
    Server --> Chainlit["Chainlit UI :8080"]
```

1. **에이전트 프로필 (`AGENT_METADATA`)**:
   - `name`: 시스템 내부 식별자 및 URL 경로 (`/agents/chatbot/invoke`)
   - `description`: Chainlit UI 상단 프로필 선택 메뉴에 노출되는 설명문
2. **시스템 프롬프트 (`CHATBOT_SYSTEM_PROMPT`)**:
   - 에이전트의 역할(친근한 고양이 페르소나), 응답 언어(한국어), 산출물 저장 규칙(`artifacts/` 하위)을 규정
3. **단기 기억 (`AsyncSqliteSaver` 체크포인터)**:
   - 각 대화 세션(`thread_id`)의 메시지 히스토리를 SQLite DB(`app/database/checkpoints.db`)에 지속적으로 스냅샷 저장하여 멀티턴 대화 맥락 유지
4. **도구 (`active_tools`)**:
   - LLM이 호출할 수 있는 함수 목록 (파일 읽기/쓰기, 웹 검색 등)

---

## 🛠️ 실습 단계별 수행 가이드

### 1단계: 백엔드 서버 및 Chainlit UI 실행하기

GitHub Codespaces 터미널을 2개 열고 아래 명령어를 순서대로 실행합니다.

#### 터미널 ①: FastAPI 백엔드 서버 실행
```bash
python app/server.py --port 8000
```
> [!NOTE]
> 서버가 기동되면서 `app/agents/` 내의 에이전트 파일들을 동적으로 감지하고, `http://localhost:8000/health` 및 `http://localhost:8000/agents` 엔드포인트를 통해 에이전트 레지스트리를 제공합니다.

#### 터미널 ②: Chainlit 웹 채팅 UI 실행
```bash
chainlit run app/chainlit_ui.py --port 8080
```

---

### 2단계: 웹 브라우저 접속 및 에이전트 선택

1. GitHub Codespaces 하단의 **포트(Ports)** 탭에서 **`8080` 포트**의 지구본 아이콘(Open in browser)을 클릭하여 브라우저 창을 엽니다.
2. 로그인 화면이 나타나면 아래 계정으로 로그인합니다:
   - **Username**: `user`
   - **Password**: `1234`
3. 화면 좌측 상단(또는 중앙)의 **Chat Profile** 선택 메뉴에서 **`chatbot`**을 선택합니다.
   - `chatbot.py`의 `AGENT_METADATA["description"]`에 적힌 설명문이 그대로 표출되는 것을 확인하세요!

---

### 3단계: 하네스 4대 요소 동작 검증 대화 나누기

이제 대화창에 메시지를 입력하면서 각 하네스 요소가 어떻게 작동하는지 검증합니다.

#### 🧪 테스트 1: 시스템 프롬프트(페르소나) 검증
* **사용자 입력**: `안녕! 넌 누구고 어떤 일을 할 수 있니?`
* **관찰 포인트**: 
  - `CHATBOT_SYSTEM_PROMPT`에 지정된 귀여운 고양이 말투(예: "~냥", "야옹" 등)로 재치있게 답변하는지 확인합니다.

#### 🧪 테스트 2: 단기 기억(Short-term Memory) 검증
* **사용자 입력 1**: `내 이름은 김철수이고, 내가 제일 좋아하는 음식은 마라탕이야. 꼭 기억해줘!`
* **사용자 입력 2**: `오늘 저녁 메뉴 추천해줘! 아 참, 내가 방금 내 이름이 뭐라고 했고 무슨 음식을 좋아한다고 했지?`
* **관찰 포인트**:
  - `AsyncSqliteSaver` 체크포인터가 대화 맥락을 스냅샷으로 보존하여, 이전 턴에서 제공한 사용자 정보를 정확히 회상하여 답변에 반영하는지 확인합니다.

#### 🧪 테스트 3: 세션 격리(Session Isolation) 검증
* 좌측 사이드바 상단의 **`New Chat` (+ 버튼)**을 클릭하여 완전히 새로운 대화방을 시작합니다.
* **사용자 입력**: `내 이름이 뭔지 기억나?`
* **관찰 포인트**:
  - 새 대화방에서는 새로운 `thread_id`가 발급되므로 이전 대화방의 단기 기억이 격리되어 "아직 이름을 알려주지 않았다냥!"이라고 답해야 정상입니다.

---

## 🏆 Mission 00 완료 체크리스트

- [ ] FastAPI 서버(`:8000`)와 Chainlit UI(`:8080`)가 오류 없이 실행되었다.
- [ ] Chainlit 프로필 목록에서 `chatbot`이 정상 노출되고 선택된다.
- [ ] 고양이 페르소나 시스템 프롬프트가 응답 스타일에 적용됨을 확인했다.
- [ ] 동일 세션 내에서 사용자의 이전 발화를 기억하는 단기 메모리(Checkpointer) 동작을 확인했다.
- [ ] 신규 세션 생성 시 대화 맥락이 독립적으로 격리됨을 확인했다.

축하합니다! 이제 에이전트의 최소 하네스 구조를 이해하셨습니다.  
다음 [Mission 01](./01_mission_add_custom_tool.md)로 이동하여, 이 챗봇에게 **나만의 커스텀 도구(Tool)**를 직접 만들어 장착해 봅시다!
