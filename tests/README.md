# 🧪 Agent Harness Engineering — 미션 검증 테스트 (Mission Test Suite)

본 디렉토리는 각 미션(Mission 01 ~ Mission 07) 수행 결과와 최종 통합 하네스를 자동으로 검증하는 테스트 스크립트를 포함합니다.

---

## 🎯 미션별 단계적 진도 검증 스크립트

각 미션 가이드를 수행한 후 터미널에서 아래 명령어를 실행하여 구현 여부를 즉시 검증할 수 있습니다:

| 테스트 파일 | 대응 미션 | 검증 대상 | 실행 명령어 |
| :--- | :--- | :--- | :--- |
| **`tests/test_mission01.py`** | Mission 01 | `custom_tools.py` 도구 2종(`roll_dice`, `convert_currency`) 및 `chatbot.py` 바인딩 검증 | `python tests/test_mission01.py` |
| **`tests/test_mission02.py`** | Mission 02 | `main_agent` 자가 복구 미들웨어 3종 & 도구 바인딩 결합 검증 | `python tests/test_mission02.py` |
| **`tests/test_mission03.py`** | Mission 03 | `main_agent` 5-Layer 프롬프트 조립 & 계층형 메모리(Semantic/Episodic) + **실물 시각화** | `python tests/test_mission03.py` |
| **`tests/test_mission04.py`** | Mission 04 | `skills/` 동적 확장 & `PromptAssembler` Layer 2.2 자동 주입 + **실물 시각화** | `python tests/test_mission04.py` |
| **`tests/test_mission05.py`** | Mission 05 | Human-in-the-Loop (`roll_dice` 타깃 권한 게이트 & 승인/거절 재개) | `python tests/test_mission05.py` |
| **`tests/test_mission06.py`** | Mission 06 | Guardrails (입력 보안 필터 — 프롬프트 인젝션·탈옥 선제 차단) | `python tests/test_mission06.py` |
| **`tests/test_mission07.py`** | Mission 07 | Logging & Observability (`AgentLogTracer` 감사 궤적 적재 & 세션 통계 분석) | `python tests/test_mission07.py` |
| **`tests/test_final.py`** | 최종 통합 | 전 하네스(도구 19종 + 메모리 + 가드레일 + HITL + 감사 로깅) E2E 졸업 검증 | `python tests/test_final.py` |

---

## 🚀 실행 방법

프로젝트 루트 디렉토리에서 아래 명령어로 실행하세요:

```bash
# 미션별 개별 검증 (Mission 01 ~ 07)
python tests/test_mission01.py
python tests/test_mission02.py
python tests/test_mission03.py
python tests/test_mission04.py
python tests/test_mission05.py
python tests/test_mission06.py
python tests/test_mission07.py

# 전 과정 완료 후 최종 통합 졸업 검증 (6/6)
python tests/test_final.py
```
