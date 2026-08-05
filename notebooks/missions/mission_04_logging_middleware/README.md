# 🪵 Mission 04: Logging Middleware

## 1. 개요 (Overview)
실무에서 배포된 에이전트가 오작동하거나 속도가 느려질 때, 그 내부 추론 궤적(Trajectory)과 도구 호출(Tool Call)의 상세 지연 시간(Latency)을 투명하게 관측할 수 있어야 합니다. 본 미션의 목표는 에이전트 실행 수명 주기(Lifecycle)를 가로채는 **`AgentMiddleware`**를 구현하여 실시간 로깅 및 감사 추적(Audit Trail) 파이프라인을 구축하는 것입니다.

---

## 2. 학습 목표 (Learning Objectives)
*   LangChain AgentMiddleware의 생명 주기 훅(`before_agent`, `after_agent`, `wrap_tool_call`)의 격발 순서와 작동 원리를 학습합니다.
*   멀티 스레드 및 비동기 환경에서 동시 요청이 들어와도 로그 변수가 꼬이지 않도록 파이썬 표준 라이브러리 `contextvars`를 사용하는 방법을 익힙니다.
*   호출 시 전달되는 `runtime.context` 설정을 읽어 로깅 활성화 여부(True/False) 및 저장 경로를 동적으로 수혈받는 기법을 배웁니다.

---

## 3. 미션 가이드 및 요구사항 (Mission Requirements)

### [태스크 1] 수명 주기 훅 구현
*   `LoggingMiddleware` 클래스가 `AgentMiddleware`를 상속하도록 선언합니다.
*   **시작 지점 (`before_agent`):**
    *   `runtime.context.logging_enabled` 값을 읽어 로깅이 켜진 경우에만 진행합니다.
    *   현재 시각(`time.time()`)을 `contextvars.ContextVar`를 이용해 기록합니다.
    *   사용자의 마지막 질문 내용을 읽어 콘솔에 로그(`🪵 [LoggingMiddleware] === 에이전트 실행 시작 ===`)를 출력합니다.
*   **완료 지점 (`after_agent`):**
    *   로깅이 켜진 경우, `before_agent`에서 저장했던 시작 시각을 읽어 소요 시간(Latency)을 밀리초(ms) 단위로 계산합니다.
    *   에이전트가 거쳐간 최종 답변 및 전체 대화 메세지 이력을 파싱합니다.
    *   지정된 로그 파일 경로(`self.log_path`)에 JSON 라인(`jsonl`) 형태로 감사 로그를 한 줄씩 덧붙여 기록(`_append_log`)합니다.
*   **도구 격발 시점 (`wrap_tool_call`):**
    *   도구 호출이 발생하기 전과 완료된 후의 시각을 재어 각 도구별 수행 시간을 구하고 감사 로그에 함께 기록합니다.

### [태스크 2] 서버/에이전트에 미들웨어 연결
*   본 폴더에서 `logging_middleware.py` 파일을 완성한 후, 해당 파일을 `app/middleware/logging_middleware.py` 경로로 복사하여 덮어씁니다 (기존 솔루션 코드를 대체하여 교육생 본인의 코드로 테스트합니다).
*   `app/agents/harness_agent.py`에서 `LoggingMiddleware`가 해당 모듈로부터 정상 주입되고 있고, Streamlit UI 상에서 로깅 스위치를 켰을 때 감사 로그가 `./artifacts/agent_audit_trail.json` 파일에 실시간 적재되는지 검증합니다.

---

## 4. 실습 코드 가이드 (Jupyter Notebook Skeleton)
`notebooks/missions/mission_04_logging_middleware/skeleton.ipynb` 노트북 파일 내 빈 칸들을 채워 수명 주기 감사 미들웨어를 정상 작동시키세요.
