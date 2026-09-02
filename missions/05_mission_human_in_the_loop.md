# 🎯 Mission 05: Human-in-the-Loop (권한 제어 & 인터럽트 게이트)

본 미션은 `6.Human_in_the_Loop.ipynb`에서 학습한 **도구 보안 등급제(Security Tiering)와 `HumanInTheLoopMiddleware`**를 바탕으로, 에이전트가 특정 도구를 실행하기 전 **사용자의 명시적 승인(Approve) / 거절(Reject)을 요구하는 권한 게이트(Permission Gate)**를 설정하고, **Chainlit 웹 UI에서 대화형 승인 팝업과 재개(Resume) 루프**를 검증하는 실습 과제입니다.

---

## 💡 왜 `roll_dice` 비주류 도구에 격발하는가?

실무 환경에서 HITL을 파일 쓰기나 셸 실행 같은 범용 도구에 무분별하게 걸면, 에이전트의 자율 작업(계획 수립, 메모리 요약, 웹 탐색) 루프가 매번 멈춰서 사용자 경험을 해치게 됩니다.

따라서 본 실습에서는 다른 에이전트 작업 흐름을 일체 방해하지 않는 **안전한 비주류 커스텀 도구인 `roll_dice`(주사위 굴리기)**를 타깃으로 지정하여, 권한 게이트의 인터럽트와 승인/거부 메커니즘을 깔끔하고 직관적으로 학습합니다.

| 구분 | 일반 도구 (Auto-Execution) | HITL 대상 도구 (`roll_dice`) |
| :--- | :--- | :--- |
| **실행 방식** | 에이전트가 자율적으로 판단하여 즉시 실행 | 런타임이 즉시 중단(`__interrupt__`)되고 사용자에게 권한 요청 |
| **사용자 개입** | 없음 (완전자율) | **[✅ 승인]**, **[✅ 항상 승인]**, **[❌ 거부]** 버튼 선택 |
| **결과 반영** | 함수 실행 반환값 모델에 전달 | 승인 시에만 함수 실행 / 거부 시 도구 취소 피드백 전달 |

---

## 📂 실습 대상 파일

* **런타임 설정 파일**: [`configs/hitl.config`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/configs/hitl.config)  
  👉 HITL 활성화 여부(`hitl_enabled`) 및 인터럽트 대상 도구(`interrupt_on`)를 제어합니다.
* **에이전트 정의 파일**: [`app/agents/main_agent.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/app/agents/main_agent.py)  
  👉 `active_tools`에 `roll_dice`를 포함하고, `HumanInTheLoopMiddleware`를 동적으로 마운트합니다.
* **웹 프론트엔드 연동**: [`app/chainlit_ui.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/app/chainlit_ui.py)  
  👉 SSE 스트림을 통해 `__interrupt__` 이벤트를 수신하면 `cl.AskActionMessage`로 인터랙티브 버튼을 띄웁니다.
* **자동화 검증 스크립트**: [`tests/test_mission05.py`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/tests/test_mission05.py)

---

## 🛠️ 단계별 수행 가이드

### 1단계: `configs/hitl.config` 활성화하기

[`configs/hitl.config`](file:///c:/Users/hyoun/Desktop/working_project/harness_lecture/main/agent_lab/configs/hitl.config) 파일을 열고 `"hitl_enabled": true`로 변경합니다:

```json
{
  "hitl_enabled": true,
  "interrupt_on": {
    "roll_dice": {
      "allowed_decisions": ["approve", "reject"]
    }
  }
}
```

---

### 2단계: `app/agents/main_agent.py` 미들웨어 마운트 확인

`main_agent.py`는 초기화 시 `hitl.config`를 읽어 `hitl_enabled: true`인 경우 `HumanInTheLoopMiddleware`를 자동으로 미들웨어 파이프라인에 결합합니다:

```python
# app/agents/main_agent.py 내부
from app.tools.custom_tools import roll_dice, convert_currency
from langchain.agents.middleware import HumanInTheLoopMiddleware

# 1. roll_dice 도구 바인딩
active_tools = list(tools_supervisor) + list(memory_tools) + [roll_dice, convert_currency]

# 2. HITL 미들웨어 동적 구성
hitl_cfg = _load_config("./configs/hitl.config", {"hitl_enabled": False})
if hitl_cfg.get("hitl_enabled"):
    interrupt_on = hitl_cfg.get("interrupt_on", {})
    middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))
```

---

### 3단계: 자동화 검증 스크립트 실행

터미널에서 아래 테스트를 실행하여 인터럽트 발생 및 승인/거부 재개가 정상 동작하는지 확인합니다:

```bash
python tests/test_mission05.py
```

#### ✅ 기대 성공 출력:
```text
======================================================================
🧪 [Mission 05] Human-in-the-Loop (roll_dice 권한 게이트) 검증 시작
======================================================================
  ✅ Test 1 통과: configs/hitl.config 규격 및 roll_dice 타깃 인터럽트 설정 확인
  ✅ Test 2 통과: main_agent 내 roll_dice 도구 등록 확인
  ✅ Test 3 통과: 주사위 굴리기 요청 시 __interrupt__ 정상 발생 및 페이로드 검증
  ✅ Test 4 통과: [승인(Approve)] 결정 주입 시 정상 재개 및 주사위 실행 완료
  ✅ Test 5 통과: [거부(Reject)] 결정 주입 시 도구 미실행 및 거절 응답 완료

======================================================================
🎉 [Mission 05] Human-in-the-Loop (roll_dice 권한 게이트) 100% 통과!
```

---

### 4단계: Chainlit 웹 UI에서 대화형 인터랙션 검증

터미널에서 서버와 Chainlit UI를 띄우고 브라우저(`http://localhost:8080`)에서 `main_agent`를 선택합니다:

```bash
python app/server.py --port 8000
chainlit run app/chainlit_ui.py --port 8080
```

#### 🎲 시나리오 A: 주사위 굴리기 승인 (Approve)
1. **사용자 입력**:
   ```text
   심심한데 주사위 2개 굴려줘!
   ```
2. **화면 관찰 (✨ 킬러 기능)**:
   - 에이전트가 멈추고 채팅창 하단에 권한 요청 카드와 함께 3개의 버튼이 나타납니다:
     - `[✅ 승인]`
     - `[✅ 항상 승인]`
     - `[❌ 거부]`
3. **`[✅ 승인]` 버튼 클릭**:
   - 에이전트가 즉시 재개(Resume)되며 주사위를 굴리고 결과를 반환합니다:
     `"🎲 주사위 2개(d6) 결과: [3, 5] (합계: 8)"`

---

#### 🛑 시나리오 B: 주사위 굴리기 거부 (Reject)
1. **사용자 입력**:
   ```text
   이번에는 주사위 4개 굴려줘.
   ```
2. **권한 팝업에서 `[❌ 거부]` 버튼 클릭**:
   - 에이전트가 주사위를 굴리지 않고 안전하게 실행을 중단하며 사용자에게 거절 피드백을 전달합니다:
     `"주사위 굴리기 도구 실행이 사용자에 의해 취소되었습니다. 다른 도움이 필요하시면 말씀해 주세요!"`

---

## 🏆 Mission 05 완료 체크리스트

- [ ] 도구 보안 등급제(Security Tiering)와 권한 게이트(HITL) 원리를 이해했다.
- [ ] `configs/hitl.config`에서 `roll_dice`를 인터럽트 대상으로 설정했다.
- [ ] `python tests/test_mission05.py`를 실행하여 5개 단위 테스트를 100% 통과했다.
- [ ] Chainlit UI에서 주사위 굴리기 시 승인/거부 팝업이 뜨고 결정에 따라 안전하게 재개됨을 확인했다.
