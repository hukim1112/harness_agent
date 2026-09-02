# 🧪 Prompt & Memory Harness 종합 테스트 결과 리포트

- **테스트 일시**: `2026-08-31 03:36:36`
- **테스트 환경**: Python 3.12 (WSL Ubuntu) + LangChain 1.3.15 + Gemini 3.7 Flash
- **최종 결과**: **39/39 PASS** (성공률 100%)
- **총 소요 시간**: `0.65초`

---

## 📊 스위트별 요약 테이블

| 스위트명 | 통과 수 | 총 항목 | 소요 시간 | 상태 |
| :--- | :---: | :---: | :---: | :---: |
| **Test 01: 5-Layer Prompt Assembly** | 9 | 9 | 0.00s | 🟢 PASS |
| **Test 02: Semantic Memory Store** | 9 | 9 | 0.01s | 🟢 PASS |
| **Test 03: Episodic Memory Store** | 14 | 14 | 0.26s | 🟢 PASS |
| **Test 04: Middleware + Tool 통합** | 7 | 7 | 0.38s | 🟢 PASS |
| **TOTAL** | **39** | **39** | **0.65s** | **🎉 ALL PASS** |

---

## 🔍 세부 테스트 항목별 실행 결과

### 🟢 Test 01: 5-Layer Prompt Assembly (9/9)

- ✅ **`test_01_l1_system_identity`**
  - **상세**: L1 시스템 아이덴티티 블록 최상단 위치 확인
- ✅ **`test_02_l2_tool_alphabetical_sort`**
  - **상세**: 도구 순서: alpha(169) < middle(234) < zebra(300)
- ✅ **`test_03_boundary_marker_position`**
  - **상세**: Boundary Marker 위치: L2(55) < Boundary(182)
- ✅ **`test_04_l3_session_context`**
  - **상세**: L3 세션 컨텍스트 (session_id, permission, project) 정상 반영
- ✅ **`test_05_l4_recalled_memory_injection`**
  - **상세**: L4에 recalled_memory만 주입 (MemoryMiddleware 경유), l4_docs 이중 주입 없음
- ✅ **`test_06_l4_no_memory_fallback`**
  - **상세**: 메모리 비활성 시 'No dynamic memory' 대체 텍스트 출력 확인
- ✅ **`test_07_l5_project_rules`**
  - **상세**: L5 프로젝트 규칙 (CLAUDE.md) 정상 반영
- ✅ **`test_08_merge_system_single_message`**
  - **상세**: merge_system=True: L1~L5 + Boundary가 단일 텍스트에 모두 포함
- ✅ **`test_09_layer_order_integrity`**
  - **상세**: 레이어 순서 정상: L1(4) → L2(59) → Boundary(186) → L3(226) → L4(364) → L5(477)

### 🟢 Test 02: Semantic Memory Store (9/9)

- ✅ **`test_01_add_basic`**
  - **상세**: 엔트리 추가 성공 + memory_entries 반영 확인
- ✅ **`test_02_add_duplicate`**
  - **상세**: 중복 추가 차단 + 리스트에 1개만 존재
- ✅ **`test_03_replace`**
  - **상세**: old_text 매칭 → 교체 + 원본 제거 확인
- ✅ **`test_04_remove`**
  - **상세**: 부분 문자열 매칭 삭제 성공 + entries 빈 리스트 확인
- ✅ **`test_05_capacity_limit`**
  - **상세**: 용량 초과 에러: Memory at 12/50 chars. Adding this entry (100 chars) would e
- ✅ **`test_06_frozen_snapshot_immutable`**
  - **상세**: load_from_disk() 이후 add해도 format_for_prompt() 불변 확인
- ✅ **`test_07_disk_persistence`**
  - **상세**: 새 인스턴스 재로드 시 memory + user 엔트리 모두 복원
- ✅ **`test_08_format_for_prompt_structure`**
  - **상세**: 포맷: 헤더 + 구분선 + 사용량 + 엔트리 2개 포함 (169 chars)
- ✅ **`test_09_user_store_independent`**
  - **상세**: memory/user 스토어 독립성 확인 (크로스 오염 없음)

### 🟢 Test 03: Episodic Memory Store (14/14)

- ✅ **`test_01_db_init`**
  - **상세**: SQLite DB 파일 생성 + FTS5 테이블 초기화 완료
- ✅ **`test_02_save_messages`**
  - **상세**: 메시지 저장 2개 → 재저장 3개 (upsert) 정상
- ✅ **`test_03_finalize_with_fallback_summary`**
  - **상세**: Fallback 요약 생성: 'Conversation starting with: FastAPI에서 JWT 토큰 만료를 어떻게 처리하나요?...'
- ✅ **`test_04_fts5_search`**
  - **상세**: FTS5 검색 성공: 1개 결과, 첫 결과=session_jwt_001
- ✅ **`test_05_anchored_view_with_keyword`**
  - **상세**: Anchor('refresh token') ±1 인출: 6개 메시지, refresh 키워드 포함 확인
- ✅ **`test_06_anchored_view_tail`**
  - **상세**: Anchor 없음 → tail view: 2개 메시지 반환
- ✅ **`test_07_exclude_current_session`**
  - **상세**: exclude_session_id 적용: 결과에 session_jwt_001 미포함 (0개 결과)
- ✅ **`test_08_browse_recent_ordering`**
  - **상세**: 최신 순 정렬: [newer_session, older_session]
- ✅ **`test_09_extract_local_keywords_korean`**
  - **상세**: 한국어 핵심 명사 ['인증', '마이크로서비스', '공격'] 전부 추출 성공 (총 15개 키워드)
- ✅ **`test_10_extract_local_keywords_english`**
  - **상세**: 영어 기술어 ['JWT', 'XSS', 'Stateless'] 대소문자 보존 추출 성공
- ✅ **`test_11_extract_local_keywords_stopwords`**
  - **상세**: 불용어 필터링 정상 (누출 0건, 총 15개 키워드)
- ✅ **`test_12_merge_keywords_dedup`**
  - **상세**: 병합 결과 8개, 중복 제거 + LLM 우선 + 로컬 보충 정상
- ✅ **`test_13_fallback_uses_local_keywords`**
  - **상세**: Fallback이 로컬 키워드 사용 확인 (한글 2자 명사 + 영문 기술어 포함, 15개)
- ✅ **`test_14_local_keywords_fts5_korean_search`**
  - **상세**: 한국어 '인증' 검색 성공! 로컬 키워드가 FTS5에 정확히 색인됨

### 🟢 Test 04: Middleware + Tool 통합 (7/7)

- ✅ **`test_01_get_tools_count_and_names`**
  - **상세**: get_tools() → 2개 도구: {'memory', 'session_recall'}
- ✅ **`test_02_memory_tool_add`**
  - **상세**: memory(add) → live entries + 디스크 영속성 확인
- ✅ **`test_03_memory_tool_replace`**
  - **상세**: memory(replace) → 'dark mode' → 'light mode' 교체 확인
- ✅ **`test_04_memory_tool_remove`**
  - **상세**: memory(remove) → 'Obsolete' 엔트리 삭제 + entries 빈 리스트 확인
- ✅ **`test_05_session_recall_tool`**
  - **상세**: session_recall(anchor='checkpointer') → 4개 메시지 인출
- ✅ **`test_06_before_agent_recalled_memory_injection`**
  - **상세**: before_agent → ctx.recalled_memory 주입 (668 chars): Semantic + Episodic 포함
- ✅ **`test_07_no_double_injection`**
  - **상세**: L4에 recalled_memory만 출력, l4_docs에서 USER.md/MEMORY.md 직접 출력 없음 (이중 주입 방지)

---

## 💡 주요 검증 아키텍처 및 원칙

1. **Semantic Memory 단일 주입 원칙 (이중 주입 방지)**
   - `PromptAssembler.l4_docs`에서 `USER.md`/`MEMORY.md`를 제거하여 토큰 중복 방지.
   - `MemoryMiddleware.before_agent()`의 Frozen Snapshot이 `ctx.recalled_memory`를 통해 L4에 단일 주입됨을 보장.

2. **Episodic Memory 2-Stage JIT 회상 원칙**
   - **1단계**: `before_agent`에서 FTS5 기반 과거 세션 요약 힌트 자동 주입 (토큰 100~200개 수준 절약).
   - **2단계**: 에이전트가 필요 시 `session_recall(session_id, anchor_keyword)` 도구를 능동적으로 호출하여 원문 메시지 인출.

3. **Claude Code 5-Layer Prompt Caching 구조**
   - `Layer 1(Identity)` + `Layer 2(Alphabetical Tools)` + `⚡ Boundary Marker` ➔ 정적 프리픽스 캐시 보호.
   - `Layer 3(Session)` + `Layer 4(Memory)` + `Layer 5(Project Rules)` ➔ 동적 컨텍스트 분리 관리.

4. **AgentMiddleware 비동기/동기 100% 호환**
   - `wrap_model_call`과 `awrap_model_call` 동시 지원으로 FastAPI/Chainlit 비동기 스트리밍 환경에서 안정 동작.