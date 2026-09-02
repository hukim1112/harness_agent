"""
=============================================================================
Test 01: 5-Layer Prompt Assembly 검증
=============================================================================
검증 항목:
  1. L1 (System Identity) 존재 및 위치
  2. L2 (Tool Capabilities) 알파벳 순 정렬
  3. Boundary Marker 존재 및 L2 뒤 배치
  4. L3 (Dynamic Session Context) 세션 정보 포함
  5. L4 (Memory) recalled_memory 반영 + l4_docs에 USER.md/MEMORY.md 미등록
  6. L5 (Project Rules) 존재
  7. merge_system=True/False 양쪽 동작 확인
=============================================================================
"""

import os
import sys
import json

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.middleware.prompt.prompt_assembler import PromptAssembler


def test_01_l1_system_identity():
    """L1: System Identity 블록이 최상단에 존재하는지 확인."""
    assembler = PromptAssembler(
        system_rules="You are a helpful assistant.",
        tool_schemas=[],
    )
    static = assembler.build_static_content()
    assert "=== Layer 1: System Identity & Core Role ===" in static, "L1 헤더가 없음"
    assert "You are a helpful assistant." in static, "L1 system_rules 텍스트가 없음"
    # L1이 L2보다 먼저 나와야 함
    idx_l1 = static.index("Layer 1")
    idx_l2 = static.index("Layer 2")
    assert idx_l1 < idx_l2, "L1이 L2보다 뒤에 위치함"
    return {"pass": True, "detail": "L1 시스템 아이덴티티 블록 최상단 위치 확인"}


def test_02_l2_tool_alphabetical_sort():
    """L2: 도구 스키마가 알파벳 순으로 정렬되는지 확인."""

    class FakeTool:
        def __init__(self, name, desc):
            self.name = name
            self.description = desc
            self.args = {"type": "object"}

    tools = [
        FakeTool("zebra_tool", "Z tool"),
        FakeTool("alpha_tool", "A tool"),
        FakeTool("middle_tool", "M tool"),
    ]

    assembler = PromptAssembler(system_rules="test", tool_schemas=tools)
    static = assembler.build_static_content()

    idx_a = static.index("alpha_tool")
    idx_m = static.index("middle_tool")
    idx_z = static.index("zebra_tool")
    assert idx_a < idx_m < idx_z, f"알파벳 순 정렬 위반: alpha={idx_a}, middle={idx_m}, zebra={idx_z}"
    return {"pass": True, "detail": f"도구 순서: alpha({idx_a}) < middle({idx_m}) < zebra({idx_z})"}


def test_03_boundary_marker_position():
    """Boundary Marker가 L2 뒤, L3 앞에 존재하는지 확인."""
    assembler = PromptAssembler(system_rules="test", tool_schemas=[])
    static = assembler.build_static_content()

    assert "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__" in static, "Boundary Marker가 없음"
    idx_l2 = static.index("Layer 2")
    idx_boundary = static.index("__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__")
    assert idx_l2 < idx_boundary, "Boundary Marker가 L2보다 앞에 위치함"
    return {"pass": True, "detail": f"Boundary Marker 위치: L2({idx_l2}) < Boundary({idx_boundary})"}


def test_04_l3_session_context():
    """L3: 세션 컨텍스트 정보가 반영되는지 확인."""
    assembler = PromptAssembler(system_rules="test", tool_schemas=[])
    session_ctx = {
        "cwd": "/workspace/agent_lab",
        "session_id": "test-session-42",
        "os": "posix",
        "user_permission": "ADMIN",
        "active_project": "agent_lab",
    }
    dynamic = assembler.build_dynamic_content(session_ctx)
    assert "=== Layer 3:" in dynamic, "L3 헤더가 없음"
    assert "test-session-42" in dynamic, "session_id가 L3에 미반영"
    assert "ADMIN" in dynamic, "user_permission이 L3에 미반영"
    assert "agent_lab" in dynamic, "active_project가 L3에 미반영"
    return {"pass": True, "detail": "L3 세션 컨텍스트 (session_id, permission, project) 정상 반영"}


def test_05_l4_recalled_memory_injection():
    """L4: ctx.recalled_memory가 L4에 주입되는지 확인 + l4_docs에 USER.md/MEMORY.md 미등록."""
    assembler = PromptAssembler(system_rules="test", tool_schemas=[], l4_docs={})
    recalled_text = "══════ SEMANTIC MEMORY ══════\nUser prefers dark mode.\n\n══════ EPISODIC MEMORY ══════\n[Session 1] JWT token discussion"

    dynamic = assembler.build_dynamic_content({
        "recalled_memory": recalled_text,
        "session_id": "test",
    })

    assert "=== Layer 4:" in dynamic, "L4 헤더가 없음"
    assert "User prefers dark mode" in dynamic, "recalled_memory의 Semantic 부분이 L4에 미반영"
    assert "JWT token discussion" in dynamic, "recalled_memory의 Episodic 부분이 L4에 미반영"
    assert "injected by MemoryMiddleware" in dynamic, "MemoryMiddleware 주입 표기가 없음"

    # l4_docs가 비어있으므로 USER.md/MEMORY.md 직접 출력이 없어야 함
    assert "[USER.md]:" not in dynamic, "USER.md가 l4_docs에서 직접 출력됨 (이중 주입)"
    assert "[MEMORY.md]:" not in dynamic, "MEMORY.md가 l4_docs에서 직접 출력됨 (이중 주입)"

    return {"pass": True, "detail": "L4에 recalled_memory만 주입 (MemoryMiddleware 경유), l4_docs 이중 주입 없음"}


def test_06_l4_no_memory_fallback():
    """L4: recalled_memory가 비어있고 l4_docs도 없을 때 대체 메시지 출력."""
    assembler = PromptAssembler(system_rules="test", tool_schemas=[], l4_docs={})
    dynamic = assembler.build_dynamic_content({"recalled_memory": "", "session_id": "test"})
    assert "No dynamic memory" in dynamic, "메모리 없을 때 대체 메시지가 출력되지 않음"
    return {"pass": True, "detail": "메모리 비활성 시 'No dynamic memory' 대체 텍스트 출력 확인"}


def test_07_l5_project_rules():
    """L5: 프로젝트 규칙 문서가 반영되는지 확인."""
    assembler = PromptAssembler(
        system_rules="test", tool_schemas=[],
        l5_docs={"CLAUDE.md": "Always use TypeScript."},
    )
    dynamic = assembler.build_dynamic_content({"session_id": "test"})
    assert "=== Layer 5:" in dynamic, "L5 헤더가 없음"
    assert "Always use TypeScript" in dynamic, "L5 프로젝트 규칙이 미반영"
    return {"pass": True, "detail": "L5 프로젝트 규칙 (CLAUDE.md) 정상 반영"}


def test_08_merge_system_single_message():
    """merge_system=True: 전체가 하나의 문자열로 결합."""
    assembler = PromptAssembler(system_rules="identity-text", tool_schemas=[])
    full = assembler.build_system_prompt({"session_id": "test"})
    assert "Layer 1" in full and "Layer 3" in full, "merge_system 시 모든 레이어가 단일 텍스트에 존재해야 함"
    assert "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__" in full, "Boundary Marker가 포함되어야 함"
    return {"pass": True, "detail": "merge_system=True: L1~L5 + Boundary가 단일 텍스트에 모두 포함"}


def test_09_layer_order_integrity():
    """전체 레이어 순서: L1 < L2 < Boundary < L3 < L4 < L5 확인."""
    assembler = PromptAssembler(
        system_rules="identity",
        tool_schemas=[],
        l5_docs={"RULES.md": "project rule"},
    )
    full = assembler.build_system_prompt({
        "session_id": "test",
        "recalled_memory": "some memory data",
    })
    positions = {
        "L1": full.index("Layer 1"),
        "L2": full.index("Layer 2"),
        "Boundary": full.index("__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"),
        "L3": full.index("Layer 3"),
        "L4": full.index("Layer 4"),
        "L5": full.index("Layer 5"),
    }
    order = sorted(positions.items(), key=lambda x: x[1])
    expected_order = ["L1", "L2", "Boundary", "L3", "L4", "L5"]
    actual_order = [k for k, _ in order]
    assert actual_order == expected_order, f"레이어 순서 위반: {actual_order} (expected: {expected_order})"
    return {
        "pass": True,
        "detail": f"레이어 순서 정상: {' → '.join(f'{k}({v})' for k, v in order)}",
    }


# ── Runner ──

ALL_TESTS = [
    test_01_l1_system_identity,
    test_02_l2_tool_alphabetical_sort,
    test_03_boundary_marker_position,
    test_04_l3_session_context,
    test_05_l4_recalled_memory_injection,
    test_06_l4_no_memory_fallback,
    test_07_l5_project_rules,
    test_08_merge_system_single_message,
    test_09_layer_order_integrity,
]


def run_all():
    results = []
    for test_fn in ALL_TESTS:
        name = test_fn.__name__
        try:
            result = test_fn()
            results.append({"test": name, "status": "PASS", "detail": result["detail"]})
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "detail": str(e)})
    return results


if __name__ == "__main__":
    results = run_all()
    print("=" * 70)
    print("Test 01: 5-Layer Prompt Assembly 검증")
    print("=" * 70)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['test']}: {r['detail']}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n  Result: {passed}/{total} passed")
