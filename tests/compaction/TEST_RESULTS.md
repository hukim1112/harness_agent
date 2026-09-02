# 🗜️ Compaction & Amnesia Guard Harness 테스트 결과 보고서

**실행 일시**: `2026-08-31 03:37:59`

**전체 결과**: `ALL PASS ✅` (28/28 통과, 0.01s)

---

## 📊 테스트 스위트별 요약

| 스위트 | 테스트 수 | 통과 | 실패 | 소요 시간 | 상태 |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Test 01: Snip & Micro Compactor** | 8 | 8 | 0 | 0.01s | ✅ PASS |
| **Test 02: Context Collapse** | 5 | 5 | 0 | 0.00s | ✅ PASS |
| **Test 03: Auto & Reactive Compactor** | 5 | 5 | 0 | 0.00s | ✅ PASS |
| **Test 04: Amnesia Guard** | 7 | 7 | 0 | 0.00s | ✅ PASS |
| **Test 05: E2E Pipeline & Integration** | 3 | 3 | 0 | 0.00s | ✅ PASS |
| **TOTAL** | **28** | **28** | **0** | **0.01s** | **✅ ALL PASS** |

---

## 🧪 세부 테스트 항목

### Test 01: Snip & Micro Compactor

| 테스트 | 상태 | 세부 내용 | 소요시간 |
|:---|:---:|:---|:---:|
| `test_01_snip_compactor_age_threshold` | ✅ PASS | Turn 1~4 대화에서 2턴 이전(오래된) ToolMessage만 스텁으로 축약되는지 검증 | 0.004s |
| `test_02_snip_compactor_short_tool_preserved` | ✅ PASS | 80자 이하의 짧은 ToolMessage는 오래되었더라도 원본 보존 | 0.0s |
| `test_03_snip_compactor_preserves_attributes` | ✅ PASS | Snip 축약 시 tool_call_id와 name 메타데이터가 손실 없이 100% 보존되는지 검증 | 0.001s |
| `test_04_micro_compactor_swap_large_output` | ✅ PASS | 5,000자 초과 대형 출력이 디스크 스왑 파일로 저장되고 스텁으로 대체되는지 검증 | 0.001s |
| `test_05_micro_compactor_actionable_hint` | ✅ PASS | 스텁에 read_file / grep_search를 통한 부분 조회 액션 유도형 힌트가 포함되어 있는지 검증 | 0.001s |
| `test_06_micro_compactor_small_output_untouched` | ✅ PASS | 5,000자 이하의 일반 출력은 디스크 스왑 없이 원본 유지 | 0.002s |
| `test_07_micro_compactor_swap_file_integrity` | ✅ PASS | 생성된 스왑 파일이 디스크에 존재하며 원본 데이터와 100% 일치하는지 검증 | 0.001s |
| `test_08_micro_compactor_multi_swaps_unique` | ✅ PASS | 복수 개의 대형 출력이 발생했을 때 각각 고유한 스왑 파일로 분리 생성되는지 검증 | 0.001s |

### Test 02: Context Collapse

| 테스트 | 상태 | 세부 내용 | 소요시간 |
|:---|:---:|:---|:---:|
| `test_01_collapse_3_consecutive_steps` | ✅ PASS | 3개의 연속된 ToolMessage가 1개의 Collapsed SystemMessage로 접히는지 검증 | 0.001s |
| `test_02_collapse_less_than_threshold_untouched` | ✅ PASS | 2개 이하의 도구 호출은 min_consecutive(3) 미만이므로 접히지 않고 원본 유지 | 0.001s |
| `test_03_collapse_mixed_ai_thought_and_tools` | ✅ PASS | AIMessage(tool_calls)와 ToolMessage가 교차하는 8단계 리서치 블록 전체 접기 검증 | 0.001s |
| `test_04_collapse_snapshot_disk_backup` | ✅ PASS | 접힌 8단계의 원본 트랜스크립트가 collapse_snap_*.txt에 온전히 백업되는지 검증 | 0.001s |
| `test_05_collapse_preserves_surrounding_dialogue` | ✅ PASS | 연속 탐색 구간 앞뒤의 일반 사용자 질의 및 AI 응답이 정확히 보존되는지 검증 | 0.001s |

### Test 03: Auto & Reactive Compactor

| 테스트 | 상태 | 세부 내용 | 소요시간 |
|:---|:---:|:---|:---:|
| `test_01_auto_compactor_below_threshold_no_op` | ✅ PASS | 토큰 수가 임계치(8,000) 이하일 때는 요약하지 않고 원본 유지 | 0.0s |
| `test_02_auto_compactor_above_threshold_summary` | ✅ PASS | 토큰 임계치 초과 시 이전 대화 전체가 4-Section 요약으로 압축되는지 검증 | 0.0s |
| `test_03_auto_compactor_fallback_on_llm_error` | ✅ PASS | LLM 호출 중 예외 발생 시 에러가 중단되지 않고 Fallback 요약이 생성되는지 검증 | 0.0s |
| `test_04_reactive_compactor_handles_413_slicing` | ✅ PASS | 413 에러 발생 시 오래된 대화 메시지의 20%를 잘라내고 재구성하는지 검증 | 0.0s |
| `test_05_reactive_compactor_short_dialogue_fallback` | ✅ PASS | 대화 메시지가 2개 이하로 극단적으로 짧은 상태에서 오버플로우 발생 시 페이로드 직접 자르기 | 0.0s |

### Test 04: Amnesia Guard

| 테스트 | 상태 | 세부 내용 | 소요시간 |
|:---|:---:|:---|:---:|
| `test_01_track_file_access_lru` | ✅ PASS | 최근 파일 경로가 LRU(가장 최근 접근한 파일이 끝으로 이동)로 관리되는지 검증 | 0.0s |
| `test_02_track_file_access_max_limit` | ✅ PASS | max_restore_files(예: 2개)를 초과할 경우 오래된 파일이 삭제되는지 검증 | 0.0s |
| `test_03_set_active_plan` | ✅ PASS | 활성 계획 텍스트 보존 및 갱신 검증 | 0.0s |
| `test_04_create_recovery_attachments_files_and_plan` | ✅ PASS | 디스크 실제 파일 내용과 활성 계획이 SystemMessage 복원 블록으로 생성되는지 검증 | 0.001s |
| `test_05_amnesia_tool_interceptor_wrap_tool_call` | ✅ PASS | @wrap_tool_call 인터셉터가 write_file, update_plan 도구 호출 시 인자를 자동 캡처하는지 검증 | 0.0s |
| `test_06_amnesia_guard_integrated_with_auto_compactor` | ✅ PASS | AutoCompactor 실행 시 AmnesiaGuard의 복원 블록이 요약 메시지 바로 뒤에 주입되는지 검증 | 0.001s |
| `test_07_amnesia_guard_integrated_with_reactive_compactor` | ✅ PASS | ReactiveCompactor 실행 시 AmnesiaGuard의 복원 블록이 정상 주입되는지 검증 | 0.001s |

### Test 05: E2E Pipeline & Integration

| 테스트 | 상태 | 세부 내용 | 소요시간 |
|:---|:---:|:---|:---:|
| `test_01_phase1_sequential_pipeline_execution` | ✅ PASS | Snip, Micro, Collapse, Auto가 Phase 1 파이프라인에서 순차적으로 모두 적용되는지 검증 | 0.001s |
| `test_02_phase2_reactive_retry_on_413` | ✅ PASS | Handler에서 413 에러 발생 시 ReactiveCompactor가 포획하여 20% Tail Slicing 후 자동 재시도하는지 검증 | 0.001s |
| `test_03_micro_swap_and_actionable_file_inspection_flow` | ✅ PASS | MicroCompactor로 스왑된 파일 경로에서 필요한 부분을 read_file 슬라이스로 읽는 서브 플로우 검증 | 0.001s |
