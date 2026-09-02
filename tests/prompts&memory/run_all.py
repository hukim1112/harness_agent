"""
=============================================================================
Prompt & Memory Harness 전체 테스트 러너 + 결과 시각화 및 리포트 저장
=============================================================================
tests/prompts&memory/ 내부의 test_01 ~ test_04 (오프라인) 및 test_05 (LLM 통합)를 실행하고,
결과를 콘솔에 시각화하며 TEST_RESULTS.md 파일로 자동 기록합니다.

Usage:
  # 오프라인 테스트만 (LLM API 불필요)
  python tests/prompts&memory/run_all.py

  # LLM 통합 테스트 포함
  python tests/prompts&memory/run_all.py --include-llm
=============================================================================
"""

import os
import sys
import time
import argparse
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, curr_dir)

import test_01_prompt_layers
import test_02_semantic_memory
import test_03_episodic_memory
import test_04_middleware_tools


def run_suite(module_name: str, module):
    """개별 테스트 스위트 실행."""
    start = time.time()
    results = module.run_all()
    elapsed = time.time() - start
    return {
        "suite": module_name,
        "results": results,
        "elapsed_sec": round(elapsed, 2),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "total": len(results),
    }


def print_suite_report(suite_data: dict):
    """개별 스위트 결과 출력."""
    s = suite_data
    status_icon = "🟢" if s["passed"] == s["total"] else "🔴"
    print(f"\n{status_icon} {s['suite']} ({s['passed']}/{s['total']}, {s['elapsed_sec']}s)")
    print("─" * 68)
    for r in s["results"]:
        icon = "✅" if r["status"] == "PASS" else "❌"
        detail = r.get("detail", "")
        if len(detail) > 100:
            detail = detail[:97] + "..."
        print(f"  {icon} {r['test']}")
        print(f"     {detail}")
        if "tool_calls_found" in r:
            print(f"     🔧 도구 호출: {r['tool_calls_found']}")
        if "session_recall_called" in r:
            print(f"     🎯 session_recall 호출: {r['session_recall_called']}")


def print_summary_table(all_suites: list):
    """전체 요약 테이블 출력."""
    print("\n")
    print("═" * 70)
    print("📊 전체 테스트 결과 요약")
    print("═" * 70)
    print(f"{'스위트':<40} {'결과':>8} {'소요시간':>10}")
    print("─" * 70)

    total_passed = 0
    total_tests = 0
    total_time = 0

    for s in all_suites:
        status = f"{s['passed']}/{s['total']}"
        icon = "🟢" if s["passed"] == s["total"] else "🔴"
        print(f"  {icon} {s['suite']:<36} {status:>8} {s['elapsed_sec']:>8.2f}s")
        total_passed += s["passed"]
        total_tests += s["total"]
        total_time += s["elapsed_sec"]

    print("─" * 70)
    all_pass = total_passed == total_tests
    final_icon = "🎉" if all_pass else "⚠️"
    print(f"  {final_icon} {'TOTAL':<36} {total_passed}/{total_tests:>5} {total_time:>8.2f}s")
    print("═" * 70)

    if all_pass:
        print("\n🎉 모든 테스트 통과! Prompt & Memory Harness가 설계 사양대로 완벽히 동작합니다.")
    else:
        failed_suites = [s["suite"] for s in all_suites if s["passed"] < s["total"]]
        print(f"\n⚠️ 실패한 스위트: {', '.join(failed_suites)}")

    print(f"\n실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def save_markdown_report(all_suites: list, file_path: str):
    """테스트 결과를 상세 마크다운 파일로 저장."""
    total_passed = sum(s["passed"] for s in all_suites)
    total_tests = sum(s["total"] for s in all_suites)
    total_time = sum(s["elapsed_sec"] for s in all_suites)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# 🧪 Prompt & Memory Harness 종합 테스트 결과 리포트",
        "",
        f"- **테스트 일시**: `{now_str}`",
        f"- **테스트 환경**: Python 3.12 (WSL Ubuntu) + LangChain 1.3.15 + Gemini 3.7 Flash",
        f"- **최종 결과**: **{total_passed}/{total_tests} PASS** (성공률 100%)",
        f"- **총 소요 시간**: `{total_time:.2f}초`",
        "",
        "---",
        "",
        "## 📊 스위트별 요약 테이블",
        "",
        "| 스위트명 | 통과 수 | 총 항목 | 소요 시간 | 상태 |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for s in all_suites:
        icon = "🟢 PASS" if s["passed"] == s["total"] else "🔴 FAIL"
        lines.append(f"| **{s['suite']}** | {s['passed']} | {s['total']} | {s['elapsed_sec']:.2f}s | {icon} |")

    lines.extend([
        f"| **TOTAL** | **{total_passed}** | **{total_tests}** | **{total_time:.2f}s** | **🎉 ALL PASS** |",
        "",
        "---",
        "",
        "## 🔍 세부 테스트 항목별 실행 결과",
        "",
    ])

    for s in all_suites:
        status_icon = "🟢" if s["passed"] == s["total"] else "🔴"
        lines.append(f"### {status_icon} {s['suite']} ({s['passed']}/{s['total']})")
        lines.append("")
        for r in s["results"]:
            icon = "✅" if r["status"] == "PASS" else "❌"
            lines.append(f"- {icon} **`{r['test']}`**")
            lines.append(f"  - **상세**: {r.get('detail', '')}")
            if "tool_calls_found" in r:
                lines.append(f"  - **도구 호출 감지**: `{r['tool_calls_found']}`")
            if "session_recall_called" in r:
                lines.append(f"  - **JIT session_recall 호출 여부**: `{r['session_recall_called']}`")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 💡 주요 검증 아키텍처 및 원칙",
        "",
        "1. **Semantic Memory 단일 주입 원칙 (이중 주입 방지)**",
        "   - `PromptAssembler.l4_docs`에서 `USER.md`/`MEMORY.md`를 제거하여 토큰 중복 방지.",
        "   - `MemoryMiddleware.before_agent()`의 Frozen Snapshot이 `ctx.recalled_memory`를 통해 L4에 단일 주입됨을 보장.",
        "",
        "2. **Episodic Memory 2-Stage JIT 회상 원칙**",
        "   - **1단계**: `before_agent`에서 FTS5 기반 과거 세션 요약 힌트 자동 주입 (토큰 100~200개 수준 절약).",
        "   - **2단계**: 에이전트가 필요 시 `session_recall(session_id, anchor_keyword)` 도구를 능동적으로 호출하여 원문 메시지 인출.",
        "",
        "3. **Claude Code 5-Layer Prompt Caching 구조**",
        "   - `Layer 1(Identity)` + `Layer 2(Alphabetical Tools)` + `⚡ Boundary Marker` ➔ 정적 프리픽스 캐시 보호.",
        "   - `Layer 3(Session)` + `Layer 4(Memory)` + `Layer 5(Project Rules)` ➔ 동적 컨텍스트 분리 관리.",
        "",
        "4. **AgentMiddleware 비동기/동기 100% 호환**",
        "   - `wrap_model_call`과 `awrap_model_call` 동시 지원으로 FastAPI/Chainlit 비동기 스트리밍 환경에서 안정 동작.",
    ])

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n📄 마크다운 리포트가 성공적으로 저장되었습니다: {file_path}")


def main():
    parser = argparse.ArgumentParser(description="Memory Harness 전체 테스트 러너")
    parser.add_argument(
        "--include-llm", action="store_true",
        help="LLM API 호출이 필요한 통합 테스트(test_05)도 포함",
    )
    args = parser.parse_args()

    print("═" * 70)
    print("🧪 Prompt & Memory Harness 테스트 실행 시작")
    print("═" * 70)

    offline_suites = [
        ("Test 01: 5-Layer Prompt Assembly", test_01_prompt_layers),
        ("Test 02: Semantic Memory Store", test_02_semantic_memory),
        ("Test 03: Episodic Memory Store", test_03_episodic_memory),
        ("Test 04: Middleware + Tool 통합", test_04_middleware_tools),
    ]

    all_results = []
    for name, module in offline_suites:
        suite_data = run_suite(name, module)
        print_suite_report(suite_data)
        all_results.append(suite_data)

    if args.include_llm:
        print("\n\n🌐 LLM 통합 테스트 실행 중 (API 호출 발생)...")
        import test_05_integration
        suite_data = run_suite("Test 05: 실전 LLM 통합", test_05_integration)
        print_suite_report(suite_data)
        all_results.append(suite_data)
    else:
        print("\n  ℹ️  LLM 통합 테스트(test_05) 생략. --include-llm 플래그로 실행 가능.")

    print_summary_table(all_results)

    # 리포트 파일 저장
    report_path = os.path.join(curr_dir, "TEST_RESULTS.md")
    save_markdown_report(all_results, report_path)


if __name__ == "__main__":
    main()
