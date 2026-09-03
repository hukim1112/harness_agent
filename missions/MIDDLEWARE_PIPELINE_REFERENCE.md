# 📋 미들웨어 파이프라인 순서 레퍼런스

Mission 02~07을 거치며 `main_agent.py`에 추가되는 미들웨어의 **최종 파이프라인 순서**를 정리한 레퍼런스입니다.  
미들웨어 삽입 순서가 헷갈릴 때 이 파일을 참고하세요.

---

## 🧩 미들웨어 실행 순서와 역할

미들웨어는 리스트 순서대로 요청을 감싸는 **러시안 인형(Matryoshka)** 구조입니다.  
리스트 앞쪽일수록 **외부 껍데기**, 뒤쪽일수록 **LLM 모델에 가까운 내부 껍데기**입니다.

```
사용자 요청 →
  [1] AgentLogTracer            (전체 라이프사이클 감사 로깅 — 가장 바깥)    ← Mission 07
  [2] InputSafetyGuardrail      (프롬프트 인젝션 / 탈옥 시도 선제 차단)      ← Mission 06
  [3] TopicAlignmentGuardrail   (오프토픽 질문 차단 & 대안 안내)            ← Mission 06
  [4] MemoryMiddleware          (메모리 컨텍스트 주입 & 세션 종료 시 인덱싱)  ← Mission 03
  [5] PromptAssemblerMiddleware (5계층 시스템 프롬프트 조립)                ← Mission 03
  [6] HumanInTheLoopMiddleware  (지정 도구 실행 전 사용자 승인 요청)         ← Mission 05
  [7] ModelFallbackMiddleware   (모델 호출 실패 시 백업 모델로 재시도)       ← Mission 02
  [8] ToolErrorHandlerMiddleware(도구 실행 오류 시 에러 메시지로 변환)       ← Mission 02
  [9] ModelCallLimitMiddleware  (무한 루프 방지 — 최대 호출 횟수 제한)       ← Mission 02
                              → LLM 모델 호출
```

---

## 💡 왜 이 순서인가?

| 위치 | 미들웨어 | 배치 이유 |
| :---: | :--- | :--- |
| 1 | **AgentLogTracer** | 가장 바깥에서 감싸야 차단된 요청 포함 **전체 라이프사이클**을 로깅 |
| 2~3 | **Guardrails** | 악의적/오프토픽 입력을 **메모리 조회 전에** 즉시 차단 → 리소스 낭비 방지 |
| 4~5 | **Memory → Prompt** | 안전이 확인된 입력만 메모리 조회 및 프롬프트 조립에 사용 |
| 6 | **HITL** | 도구 실행 **직전**에 인터럽트하여 사용자 승인을 요청 |
| 7~9 | **Self-Recovery** | LLM에 가장 가까운 내부에서 모델/도구 **장애 복구** 담당 |

---

## ✅ 미션별 누적 구성 체크리스트

### Mission 02 완료 시점 (3종)
```python
middleware = [
    ModelFallbackMiddleware(max_retries=2, initial_delay=0.5, fallback_model_name=backup_model),
    ToolErrorHandlerMiddleware(max_retries=0),
    ModelCallLimitMiddleware(run_limit=50, exit_behavior="end"),
]
```

### Mission 03 완료 시점 (5종)
```python
middleware = [
    memory_mw,                       # ← 추가 (가장 앞)
    prompt_mw,                       # ← 추가
    ModelFallbackMiddleware(...),
    ToolErrorHandlerMiddleware(...),
    ModelCallLimitMiddleware(...),
]
```

### Mission 05 완료 시점 — 파이프라인 재구성 (6종)

> [!IMPORTANT]
> Mission 05부터 **보안 거버넌스 순서**를 고려하여 파이프라인을 재구성합니다.
> 기존 `middleware = [...]` 방식에서 **빈 리스트 + 순서별 append/extend** 방식으로 전환합니다.

```python
middleware = []

# (1~3은 아직 비활성 — Mission 06, 07에서 추가됨)

# (3) Memory & Prompt Assembler
middleware.extend([memory_mw, prompt_mw])

# (4) HITL 동적 구성
if hitl_cfg.get("hitl_enabled"):
    middleware.append(HumanInTheLoopMiddleware(interrupt_on=...))   # ← 추가

# (5) Self-Recovery Circuit Breakers
middleware.extend([ModelFallback..., ToolErrorHandler..., ModelCallLimit...])
```

### Mission 06 완료 시점 (8종)
```python
middleware = []

# (2) Guardrails ← 추가 (Memory 앞에 위치!)
if guardrail_cfg.get("guardrail_enabled"):
    middleware.append(InputSafetyGuardrail(...))       # ← 추가
    middleware.append(TopicAlignmentGuardrail(...))     # ← 추가

# (3) Memory & Prompt
middleware.extend([memory_mw, prompt_mw])
# (4) HITL
# (5) Self-Recovery
```

### Mission 07 완료 시점 — 최종 (9종)
```python
middleware = []

# (1) Logging ← 추가 (가장 앞에 위치!)
if logging_cfg.get("logging_enabled"):
    middleware.append(AgentLogTracer(log_path=...))     # ← 추가

# (2) Guardrails
# (3) Memory & Prompt
# (4) HITL
# (5) Self-Recovery
```
