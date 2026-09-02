"""
=============================================================================
Agent Lab Tests Master Runner
=============================================================================
하위 테스트 패키지들을 검색하여 전체 테스트를 실행합니다.

Usage:
  python tests/run_all.py
  python tests/run_all.py --include-llm
=============================================================================
"""

import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description="Agent Lab Master Test Runner")
    parser.add_argument("--include-llm", action="store_true", help="Include live LLM integration tests")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    prompts_mem_runner = os.path.join(os.path.dirname(__file__), "prompts&memory", "run_all.py")
    compaction_runner = os.path.join(os.path.dirname(__file__), "compaction", "run_all.py")

    env = os.environ.copy()
    env["PYTHONPATH"] = project_root

    exit_codes = []

    # 1. Prompt & Memory Suite
    print(f"🚀 Running Prompt & Memory Harness Test Suite...")
    pm_cmd = [sys.executable, prompts_mem_runner]
    if args.include_llm:
        pm_cmd.append("--include-llm")
    r1 = subprocess.run(pm_cmd, env=env, cwd=project_root)
    exit_codes.append(r1.returncode)

    # 2. Compaction Suite
    print("\n" + "═" * 70)
    print(f"🚀 Running Compaction & Amnesia Guard Test Suite...")
    print("═" * 70)
    comp_cmd = [sys.executable, compaction_runner]
    r2 = subprocess.run(comp_cmd, env=env, cwd=project_root)
    exit_codes.append(r2.returncode)

    sys.exit(max(exit_codes))

if __name__ == "__main__":
    main()
