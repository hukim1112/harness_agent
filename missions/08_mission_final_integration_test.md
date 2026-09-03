# 🎓 Mission 08: Final Integration Test (전 과정 통합 졸업 검증)

Mission 00~07을 순서대로 완수하며 구축한 **프로덕션 에이전트 하네스**의 전 기능을 단일 스크립트로 한 번에 검증하는 최종 졸업 테스트입니다.

모든 항목이 ✅ 통과되면 **Agent Harness Engineering** 전 과정을 성공적으로 완수한 것입니다!

---

## 🧪 검증 항목 (7개)

| # | 검증 대상 | Mission | 테스트 내용 |
| :---: | :--- | :---: | :--- |
| 1 | 📦 에이전트 빌드 | 00~01 | `main_agent` 전체 빌드 성공 (미들웨어 + 도구 19종 바인딩) |
| 2 | 🧠 Semantic Memory | 03 | 정상 대화 시 `memory` 도구가 자율 호출되어 사용자 정보 기록 |
| 3 | 🛡️ InputSafetyGuardrail | 06 | 프롬프트 인젝션 공격(시스템 프롬프트 유출 시도) 선제 차단 |
| 4 | 🛑 TopicAlignmentGuardrail | 06 | 오프토픽 질문(정치적 평가) 차단 및 대안 안내 |
| 5 | 🎲 HITL 인터럽트 & 승인 | 05 | `roll_dice` 호출 시 인터럽트 → 승인 주입 → 정상 실행 |
| 6 | 📊 감사 로그 & 대시보드 | 07 | `AgentLogTracer` JSONL 감사 궤적 적재 + `log_analyzer` 메트릭 집계 |
| 7 | 💾 Episodic 크로스세션 | 03 | 세션 A 대화 → 세션 B에서 과거 대화 키워드 기반 회상 |

---

## ▶️ 실행 방법

### 사전 조건

Mission 00~07을 모두 완수하고, 아래 설정이 활성화되어 있어야 합니다:

```
configs/hitl.config       → "hitl_enabled": true
configs/guardrail.config  → "guardrail_enabled": true
configs/logging.config    → "logging_enabled": true
```

### 테스트 실행

```bash
python tests/test_final.py
```
---

## 💡 실패 시 디버깅 가이드

| 실패 항목 | 확인 포인트 |
| :--- | :--- |
| 📦 에이전트 빌드 | `.env` 파일에 `GOOGLE_API_KEY` 설정, `configs/model.config` 모델명 확인 |
| 🧠 Semantic Memory | `memory` 도구가 도구 세트에 포함되어 있는지, `MemoryMiddleware` 마운트 확인 |
| 🛡️ InputSafety | `configs/guardrail.config`의 `guardrail_enabled: true`, `input_safety.enabled: true` |
| 🛑 TopicAlignment | `topic_alignment.enabled: true`, `blocked_topics` 리스트 확인 |
| 🎲 HITL | `configs/hitl.config`의 `hitl_enabled: true`, `roll_dice`가 `interrupt_on`에 등록 |
| 📊 감사 로그 | `configs/logging.config`의 `logging_enabled: true`, `log_dir` 디렉토리 쓰기 권한 |
| 💾 Episodic | `EpisodicStore`가 정상 초기화, `finalize_session` 호출 후 인덱싱 완료 대기 |

---

## 🏆 Mission 08 완료 체크리스트

- [ ] `python tests/test_final.py`를 실행하여 **7/7 전체 통과**를 확인했다.
- [ ] 결과표에서 모든 항목이 ✅로 표시되었다.
- [ ] 🎉 **축하합니다! 프로덕션 하네스 엔지니어링 전 과정을 완수했습니다!**
