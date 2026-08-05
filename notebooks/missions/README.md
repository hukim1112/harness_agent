# 🚀 실무 에이전트 개발 실습 가이드 (Agent Harness Lab Missions)

본 실습 환경은 단계별로 실무급 에이전트 아키텍처(메모리, 도구, 로깅 미들웨어, 가드레일, 자가 치유)를 조립해 나가는 교육 과정입니다.

미션을 수행하기에 앞서, 아래 가이드를 통해 **백엔드 서버**와 **프론트엔드 웹 UI**를 구동하고, 기본 장착되어 있는 **`chatbot` 에이전트**와 대화하며 시스템 작동을 먼저 확인해 보십시오.

---

## 🛠️ 1. 사전 준비 (Prerequisites)

실습 환경을 실행하려면 먼저 Python 가상환경을 활성화하고 필수 API Key 설정을 점검해야 합니다.

1.  **가상환경 활성화** (터미널에서 실행):
    ```bash
    source ~/env_langchain_123/bin/activate
    ```
2.  **환경 변수 설정 확인**:
    프로젝트 루트에 있는 `.env` 파일에 AI 모델 호출에 필요한 API Key들이 정상적으로 입력되어 있는지 확인합니다.
    ```bash
    cat .env
    ```

---

## 🚀 2. 백엔드 및 웹 UI 구동 방법

개발 환경을 기동하려면 **백엔드 API 서버**와 **프론트엔드 웹 UI**를 각각 별도의 터미널 창에서 순서대로 가동해야 합니다.

### [Step 1] 백엔드 FastAPI 서버 실행
첫 번째 터미널 창에서 가상환경을 활성화한 뒤 백엔드 서버를 가동합니다.
```bash
python app/server.py
```
*   서버는 **`http://localhost:8000`** 포트에서 기동합니다.
*   서버 로그에 아래와 같이 두 에이전트가 로드되었다는 문구가 나오는지 확인합니다.
    *   `INFO:LLMOps_Server:✅ Registered agent: chatbot at /chatbot`
    *   (주의: 실습용 에이전트인 `harness_agent` 모듈은 미션 06 단계를 수행하기 전까지는 코드가 탑재되지 않아 경고 로그가 발생할 수 있으며, 이는 정상입니다.)

### [Step 2] 프론트엔드 Streamlit 웹 UI 실행
두 번째 터미널 창을 새로 열어 가상환경을 활성화한 후, 프론트엔드 UI를 실행합니다.
```bash
streamlit run app/ui.py
```
*   명령어를 실행하면 자동으로 브라우저 창이 열리며 **`http://localhost:8501`** 포트의 대화형 웹 인터페이스로 접속됩니다.

---

## 💬 3. 미션 시작 전 Chatbot과의 대화 테스트

실습 코드를 한 줄도 작성하지 않았더라도, 이미 정상 빌드되어 있는 기준 에이전트인 **`chatbot`**을 통해 UI 및 서버 연동 테스트를 즉시 진행해 볼 수 있습니다.

1.  **에이전트 선택**:
    *   웹 UI 화면 왼쪽 사이드바의 **`Agent Selection`** 셀렉트박스에서 **`chatbot`**을 선택합니다.
2.  **새 세션 만들기**:
    *   사이드바 하단의 **`[+ Create New Session]`** 버튼을 클릭하여 대화 세션을 새로 개설합니다.
3.  **대화 진행 및 도구 작동 확인**:
    *   메시지 창에 질문을 던져 대화를 나누어 보십시오 (예: *"안녕! 너에 대해 소개해줘"*).
    *   `chatbot`은 **귀여운 고양이 페르소나**로 친근하게 답변하도록 설정되어 있습니다.
    *   **도구 사용 테스트**: *"서울 날씨를 조회해줘"* 또는 *"test.txt 파일을 읽어줘"* 등 도구 호출을 수반하는 질문을 입력해 보십시오.
    *   에이전트가 도구(Tool)를 격발할 때 웹 UI 화면 하단에 **[Tool Start] / [Tool End]**와 같은 실시간 궤적이 시각화되어 렌더링되는지 확인합니다.

---

## 🎯 4. 단계별 미션 개요

준비가 완료되면 `notebooks/missions/` 폴더 내 각 미션 디렉토리에 위치한 `README.md`와 `skeleton.ipynb` 파일을 열어 다음 순서대로 실습을 진행하십시오.

1.  **`mission_01_baseline`**: `create_agent` 기반 기초 ReAct 대화형 에이전트 구조 잡기
2.  **`mission_02_Prompt_and_Caching`**: 5계층 프롬프트 및 비용 90% 감축을 위한 프롬프트 캐싱 설계
3.  **`mission_03_common_tools`**: 파일 시스템 제어, 정보 검색 등 범용 8대 도구(Tools) 연동
4.  **`mission_04_persistent_memory`**: SQLite 기반의 L1 영속 체크포인터 메모리 아키텍처 구현
5.  **`mission_05_Logging_Middleware`**: 에이전트 실행 주기 관측을 위한 감사 로깅 미들웨어 제작
6.  **`mission_06_Agent_Assembly`**: 구현한 컴포넌트들을 모아 완성형 `harness_agent` 빌드 및 서버 등록
7.  **`mission_07_SelfCorrection_and_Guardrails`**: 입력/주제 가드레일 미들웨어 및 툴 에러 자가 치유 구현
8.  **`mission_08_Awesome_Agent_Skills`**: 에이전트에 자율적이고 고급 스킬(Skills) 확장 기법 연동
