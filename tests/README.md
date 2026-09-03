# 🧪 Agent Lab 테스트 체계 (Test Suites)

본 디렉토리는 `agent_lab` 프로젝트의 핵심 하네스, 프롬프트 엔지니어링, 메모리 시스템, 컨텍스트 압축 및 에이전트 통합 동작을 체계적으로 검증하는 테스트 모듈들을 관리합니다.

---

## 🎯 미션별 단계적 진도 검증 스크립트 (Mission Tests)

교육생이 각 미션 가이드를 수행한 후 바로 자신의 코드를 검증할 수 있는 단위 테스트입니다:

| 테스트 파일 | 대응 미션 | 검증 대상 | 실행 명령어 |
| :--- | :--- | :--- | :--- |
| **`tests/test_mission01.py`** | Mission 01 | `custom_tools.py` 도구 2종 및 `chatbot.py` 바인딩 검증 | `python tests/test_mission01.py` |
| **`tests/test_mission02.py`** | Mission 02 | `main_agent.py` 자가 복구 미들웨어 3종 & 도구 15종 결합 | `python tests/test_mission02.py` |
| **`tests/test_mission03.py`** | Mission 03 | `main_agent.py` 5-Layer 프롬프트 조립 & 메모리 + **실물 시각화** | `python tests/test_mission03.py` |
| **`tests/test_mission04.py`** | Mission 04 | `skills/` 동적 확장 & `PromptAssembler` Layer 2.2 자동 주입 + **실물 시각화** | `python tests/test_mission04.py` |
| **`tests/test_mission05.py`** | Mission 05 | Human-in-the-Loop (`roll_dice` 타깃 권한 게이트 & 승인/거절 재개) | `python tests/test_mission05.py` |
| **`tests/test_mission06.py`** | Mission 06 | Guardrails (입력 보안 필터 & 주제 일치 선제 차단 및 대체 안내) | `python tests/test_mission06.py` |
| **`tests/test_mission07.py`** | Mission 07 | Logging & Observability (`AgentLogTracer` 감사 궤적 적재 & 세션 통계 분석) | `python tests/test_mission07.py` |

---

## 📂 패키지별 상세 테스트 스위트

### 1. `prompts&memory/` — 프롬프트 및 계층형 메모리 테스트
- **위치**: `tests/prompts&memory/`
- **리포트**: [`TEST_RESULTS.md`](prompts%26memory/TEST_RESULTS.md) (최신 검증 결과 리포트)
- **세부 모듈**:
  - `test_01_prompt_layers.py`: Claude Code 5계층 프롬프트 조립 및 캐시 경계 검증 (9개 항목)
  - `test_02_semantic_memory.py`: §-구분자 기반 Semantic Memory CRUD, 용량 제한, Frozen Snapshot 검증 (9개 항목)
  - `test_03_episodic_memory.py`: SQLite FTS5 전문 검색, 세션 요약, Anchor 기반 ±window 인출 검증 (8개 항목)
  - `test_04_middleware_tools.py`: MemoryMiddleware 훅 및 `memory`/`session_recall` 도구 통합 검증 (7개 항목)
  - `test_05_integration.py`: 실전 LLM(Gemini 3.7 Flash) 연동 개인화 QA, 2단계 JIT 회상, 도구 자율 쓰기 검증 (4개 항목)
  - `run_all.py`: 스위트 실행 및 시각화/마크다운 리포트 생성기

### 2. `compaction/` — 컨텍스트 압축 및 기억 보존 테스트
- **위치**: `tests/compaction/`
- **리포트**: [`TEST_RESULTS.md`](compaction/TEST_RESULTS.md) (최신 검증 결과 리포트)
- **세부 모듈**:
  - `test_01_snip_and_micro.py`: Snip & Micro-Summary 기반 토큰 절약 검증
  - `test_02_context_collapse.py`: Context Collapse 메커니즘 및 윈도우 보존 검증
  - `test_03_auto_and_reactive.py`: 임계치 초과 시 자동/반응형 압축 트리거 검증
  - `test_04_amnesia_guard.py`: 압축 중 주요 사실 유실 방지 Amnesia Guard 검증
  - `test_05_e2e_pipeline.py`: E2E 컨텍스트 압축 파이프라인 통합 검증
  - `test_06_improvements.py`: 압축 안정성 및 레이턴시 성능 개선 검증
  - `run_all.py`: 압축 스위트 일괄 실행기

---

## 🚀 테스트 실행 방법

```bash
# 1. 미션별 단위 테스트 실행 (예: Mission 01, 02)
python tests/test_mission01.py
python tests/test_mission02.py

# 2. 전체 오프라인 테스트 실행 (LLM API 호출 불필요)
PYTHONPATH=. python tests/run_all.py

# 3. 실전 LLM 통합 테스트 포함 실행
PYTHONPATH=. python tests/run_all.py --include-llm

# 4. 특정 하위 테스트만 개별 실행
PYTHONPATH=. python tests/prompts\&memory/test_01_prompt_layers.py
PYTHONPATH=. python tests/compaction/test_05_e2e_pipeline.py
```
