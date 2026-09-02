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

* **로깅 설정 파일**: [`configs/logging.config`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/configs/logging.config)  
  👉 감사 로깅 활성화 여부(`logging_enabled`) 및 로그 디렉토리(`log_dir`)를 제어합니다.
* **관측성 미들웨어**: [`app/middleware/observability/agent_log_tracer.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/app/middleware/observability/agent_log_tracer.py)  
  👉 비동기 큐 기반의 감사 궤적 수집 엔진입니다.
* **에이전트 결합 파일**: [`app/agents/main_agent.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/app/agents/main_agent.py)  
  👉 `logging.config`에 따라 `AgentLogTracer`를 미들웨어 파이프라인의 최우선 순위로 마운트합니다.
* **세션 로그 분석기**: [`app/utils/log_analyzer.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/app/utils/log_analyzer.py)  
  👉 적재된 JSONL 로그를 파싱하여 통계 대시보드를 출력하는 유틸리티입니다.
* **자동화 검증 스크립트**: [`tests/test_mission07.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/tests/test_mission07.py)

---

## 🛠️ 단계별 수행 가이드

### 1단계: `configs/logging.config` 활성화하기

[`configs/logging.config`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/configs/logging.config) 파일을 열고 `"logging_enabled": true`로 변경합니다:

```json
{
  "logging_enabled": true,
  "log_dir": "./artifacts/logs"
}
```

---

### 2단계: `app/agents/main_agent.py` 미들웨어 마운트 확인

`main_agent.py`는 `logging_enabled: true`일 때 `AgentLogTracer`를 미들웨어 파이프라인의 가장 앞단(전체 라이프사이클 캡처)에 마운트합니다:

```python
# app/agents/main_agent.py 내부
from app.middleware.observability import AgentLogTracer

logging_cfg = _load_config("./configs/logging.config", {"logging_enabled": False})
if logging_cfg.get("logging_enabled"):
    log_dir = logging_cfg.get("log_dir", "./artifacts/logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "agent_audit_trail.json")
    middleware.append(AgentLogTracer(log_path=log_path))
```

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
  ✅ Test 1 통과: configs/logging.config 규격 확인 완료
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
- [ ] `python tests/test_mission07.py`를 실행하여 단위 테스트를 100% 통과했다.
- [ ] Chainlit UI 대화 후 `python -m app.utils.log_analyzer`를 실행하여 실시간 세션 감사 통계 대시보드를 확인했다.
