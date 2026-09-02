"""
=============================================================================
Compaction Harness 전체 테스트 러너 + 결과 시각화 및 리포트 저장
=============================================================================
tests/compaction/ 내부의 test_01 ~ test_05를 실행하고,
결과를 콘솔에 시각화하며 TEST_RESULTS.md 파일로 자동 기록합니다.

Usage:
  python tests/compaction/run_all.py
=============================================================================
"""

import os
import sys
import time
import unittest
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, curr_dir)

import test_01_snip_and_micro
import test_02_context_collapse
import test_03_auto_and_reactive
import test_04_amnesia_guard
import test_05_e2e_pipeline


def run_unittest_module(module_name: str, module_obj) -> dict:
    """단일 unittest 모듈 실행 및 결과 수집"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(module_obj)
    
    start_time = time.time()
    
    results = []
    
    for test in suite:
        for t in test:
            test_name = t._testMethodName
            test_doc = t._testMethodDoc or ""
            t_start = time.time()
            res = unittest.TestResult()
            t.run(res)
            t_elapsed = round(time.time() - t_start, 3)
            
            if res.wasSuccessful():
                results.append({
                    "test": test_name,
                    "status": "PASS",
                    "detail": test_doc.strip() or "Test passed successfully",
                    "elapsed": t_elapsed
                })
            else:
                errors = res.errors + res.failures
                err_msg = str(errors[0][1]) if errors else "Failed"
                results.append({
                    "test": test_name,
                    "status": "FAIL",
                    "detail": err_msg.strip().split("\n")[-1],
                    "elapsed": t_elapsed
                })

    elapsed = round(time.time() - start_time, 2)
    return {
        "suite": module_name,
        "results": results,
        "elapsed_sec": elapsed,
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "total": len(results),
    }


def print_suite_report(suite_data: dict):
    """개별 스위트 결과 출력"""
    s = suite_data
    status_icon = "🟢" if s["passed"] == s["total"] else "🔴"
    print(f"\n{status_icon} {s['suite']} ({s['passed']}/{s['total']}, {s['elapsed_sec']}s)")
    print("─" * 68)
    for r in s["results"]:
        icon = "✅" if r["status"] == "PASS" else "❌"
        detail = r.get("detail", "")
        if len(detail) > 95:
            detail = detail[:92] + "..."
        print(f"  {icon} {r['test']}")
        print(f"     {detail}")


def print_summary_table(all_suites: list):
    """전체 요약 테이블 출력"""
    print("\n")
    print("═" * 70)
    print("📊 Compaction Harness 테스트 결과 요약")
    print("═" * 70)
    print(f"{'스위트':<42} {'결과':>8} {'소요시간':>10}")
    print("─" * 70)

    total_passed = 0
    total_tests = 0
    total_time = 0

    for s in all_suites:
        status = f"{s['passed']}/{s['total']}"
        icon = "🟢" if s["passed"] == s["total"] else "🔴"
        print(f"  {icon} {s['suite']:<38} {status:>8} {s['elapsed_sec']:>8.2f}s")
        total_passed += s["passed"]
        total_tests += s["total"]
        total_time += s["elapsed_sec"]

    print("─" * 70)
    all_pass = total_passed == total_tests
    final_icon = "🎉" if all_pass else "⚠️"
    print(f"  {final_icon} {'TOTAL':<38} {total_passed}/{total_tests:>5} {total_time:>8.2f}s")
    print("═" * 70)

    if all_pass:
        print("\n🎉 모든 테스트 통과! Compaction & Amnesia Guard Harness가 완벽히 동작합니다.")
    else:
        failed_suites = [s["suite"] for s in all_suites if s["passed"] < s["total"]]
        print(f"\n⚠️ 실패한 스위트: {', '.join(failed_suites)}")

    print(f"\n실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def save_markdown_report(all_suites: list, output_path: str):
    """마크다운 결과 리포트 저장"""
    total_passed = sum(s["passed"] for s in all_suites)
    total_tests = sum(s["total"] for s in all_suites)
    total_time = sum(s["elapsed_sec"] for s in all_suites)
    all_pass = total_passed == total_tests

    lines = [
        "# 🗜️ Compaction & Amnesia Guard Harness 테스트 결과 보고서",
        f"\n**실행 일시**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n",
        f"**전체 결과**: `{'ALL PASS ✅' if all_pass else 'SOME FAILED ❌'}` ({total_passed}/{total_tests} 통과, {total_time:.2f}s)\n",
        "---",
        "\n## 📊 테스트 스위트별 요약\n",
        "| 스위트 | 테스트 수 | 통과 | 실패 | 소요 시간 | 상태 |",
        "|:---|:---:|:---:|:---:|:---:|:---:|",
    ]

    for s in all_suites:
        icon = "✅ PASS" if s["passed"] == s["total"] else "❌ FAIL"
        failed = s["total"] - s["passed"]
        lines.append(f"| **{s['suite']}** | {s['total']} | {s['passed']} | {failed} | {s['elapsed_sec']:.2f}s | {icon} |")

    lines.append(f"| **TOTAL** | **{total_tests}** | **{total_passed}** | **{total_tests - total_passed}** | **{total_time:.2f}s** | **{'✅ ALL PASS' if all_pass else '❌ FAIL'}** |")

    lines.append("\n---\n")
    lines.append("## 🧪 세부 테스트 항목\n")

    for s in all_suites:
        lines.append(f"### {s['suite']}\n")
        lines.append("| 테스트 | 상태 | 세부 내용 | 소요시간 |")
        lines.append("|:---|:---:|:---|:---:|")
        for r in s["results"]:
            icon = "✅" if r["status"] == "PASS" else "❌"
            detail = r.get("detail", "").replace("\n", " ").replace("|", "\\|")
            lines.append(f"| `{r['test']}` | {icon} {r['status']} | {detail} | {r.get('elapsed', 0)}s |")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n📄 마크다운 리포트가 성공적으로 저장되었습니다: {output_path}")


def main():
    print("═" * 70)
    print("🧪 Compaction & Amnesia Guard Harness 테스트 실행 시작")
    print("═" * 70)

    suites_to_run = [
        ("Test 01: Snip & Micro Compactor", test_01_snip_and_micro),
        ("Test 02: Context Collapse", test_02_context_collapse),
        ("Test 03: Auto & Reactive Compactor", test_03_auto_and_reactive),
        ("Test 04: Amnesia Guard", test_04_amnesia_guard),
        ("Test 05: E2E Pipeline & Integration", test_05_e2e_pipeline),
    ]

    all_results = []
    for name, mod in suites_to_run:
        suite_res = run_unittest_module(name, mod)
        print_suite_report(suite_res)
        all_results.append(suite_res)

    print_summary_table(all_results)

    report_path = os.path.join(curr_dir, "TEST_RESULTS.md")
    save_markdown_report(all_results, report_path)

    total_passed = sum(s["passed"] for s in all_results)
    total_tests = sum(s["total"] for s in all_results)
    sys.exit(0 if total_passed == total_tests else 1)


if __name__ == "__main__":
    main()
