"""
=============================================================================
Test 02: Semantic Memory Store 검증
=============================================================================
검증 항목:
  1. CRUD: add, replace, remove 동작
  2. 중복 방지: 동일 엔트리 중복 추가 차단
  3. 용량 제한: char_limit 초과 시 에러 반환
  4. Frozen Snapshot: load_from_disk() 후 세션 중 불변
  5. 디스크 영속성: 변경 → save → 재로드 → 확인
  6. format_for_prompt() 출력 포맷 검증
=============================================================================
"""

import os
import sys
import tempfile

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.middleware.memory.semantic_store import SemanticMemoryStore


def test_01_add_basic():
    """add: 기본 엔트리 추가."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir)
        store.load_from_disk()
        r = store.add("memory", "User prefers dark mode.")
        assert r["success"] is True
        assert "User prefers dark mode." in store.memory_entries
        return {"pass": True, "detail": "엔트리 추가 성공 + memory_entries 반영 확인"}


def test_02_add_duplicate():
    """add: 동일 텍스트 중복 추가 차단."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir)
        store.load_from_disk()
        store.add("memory", "Duplicate entry.")
        r = store.add("memory", "Duplicate entry.")
        assert r["success"] is True
        assert "already exists" in r.get("message", "")
        assert store.memory_entries.count("Duplicate entry.") == 1
        return {"pass": True, "detail": "중복 추가 차단 + 리스트에 1개만 존재"}


def test_03_replace():
    """replace: old_text 매칭 → 교체."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir)
        store.load_from_disk()
        store.add("memory", "User prefers dark mode in VS Code.")
        r = store.replace("memory", "dark mode", "User prefers light mode in VS Code.")
        assert r["success"] is True
        assert "light mode" in store.memory_entries[0]
        assert "dark mode" not in store.memory_entries[0]
        return {"pass": True, "detail": "old_text 매칭 → 교체 + 원본 제거 확인"}


def test_04_remove():
    """remove: old_text 매칭 → 삭제."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir)
        store.load_from_disk()
        store.add("memory", "Temporary fact to remove.")
        assert len(store.memory_entries) == 1
        r = store.remove("memory", "Temporary fact")
        assert r["success"] is True
        assert len(store.memory_entries) == 0
        return {"pass": True, "detail": "부분 문자열 매칭 삭제 성공 + entries 빈 리스트 확인"}


def test_05_capacity_limit():
    """용량 초과 시 에러 반환."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir, memory_char_limit=50, user_char_limit=30)
        store.load_from_disk()
        store.add("memory", "Short entry.")
        r = store.add("memory", "x" * 100)
        assert r["success"] is False
        assert "exceed" in r.get("error", "").lower() or "limit" in r.get("error", "").lower()
        return {"pass": True, "detail": f"용량 초과 에러: {r.get('error', '')[:60]}"}


def test_06_frozen_snapshot_immutable():
    """Frozen Snapshot: load 후 add해도 format_for_prompt() 불변."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir)
        store.load_from_disk()
        store.add("user", "Initial profile.")
        # 스냅샷 캡처
        store.load_from_disk()
        snapshot_before = store.format_for_prompt("user")

        # 이후 변경
        store.add("user", "New info after snapshot.")
        snapshot_after = store.format_for_prompt("user")

        assert snapshot_before == snapshot_after, "Frozen Snapshot이 변경됨"
        assert "New info" not in (snapshot_after or ""), "스냅샷에 새 엔트리가 반영됨"
        return {"pass": True, "detail": "load_from_disk() 이후 add해도 format_for_prompt() 불변 확인"}


def test_07_disk_persistence():
    """디스크 영속성: save → 재로드 → 확인."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 첫 인스턴스
        store1 = SemanticMemoryStore(memory_dir=tmpdir)
        store1.load_from_disk()
        store1.add("memory", "Persistent fact A.")
        store1.add("user", "User likes Python.")

        # 새 인스턴스로 재로드
        store2 = SemanticMemoryStore(memory_dir=tmpdir)
        store2.load_from_disk()
        assert "Persistent fact A." in store2.memory_entries, "memory 엔트리 미복원"
        assert "User likes Python." in store2.user_entries, "user 엔트리 미복원"
        return {"pass": True, "detail": "새 인스턴스 재로드 시 memory + user 엔트리 모두 복원"}


def test_08_format_for_prompt_structure():
    """format_for_prompt() 출력 포맷: 헤더 + 구분선 + 사용량."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir)
        store.load_from_disk()
        store.add("memory", "Fact one.")
        store.add("memory", "Fact two.")
        store.load_from_disk()  # 스냅샷 갱신
        result = store.format_for_prompt("memory")
        assert result is not None, "format_for_prompt가 None 반환"
        assert "MEMORY" in result, "MEMORY 헤더가 없음"
        assert "═" in result, "구분선(═)이 없음"
        assert "%" in result, "사용량(%) 표시가 없음"
        assert "Fact one." in result and "Fact two." in result, "엔트리 내용이 누락"
        return {"pass": True, "detail": f"포맷: 헤더 + 구분선 + 사용량 + 엔트리 2개 포함 ({len(result)} chars)"}


def test_09_user_store_independent():
    """memory와 user 스토어가 독립적으로 동작."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SemanticMemoryStore(memory_dir=tmpdir)
        store.load_from_disk()
        store.add("memory", "Agent note.")
        store.add("user", "User preference.")
        assert "Agent note." in store.memory_entries
        assert "Agent note." not in store.user_entries
        assert "User preference." in store.user_entries
        assert "User preference." not in store.memory_entries
        return {"pass": True, "detail": "memory/user 스토어 독립성 확인 (크로스 오염 없음)"}


# ── Runner ──

ALL_TESTS = [
    test_01_add_basic,
    test_02_add_duplicate,
    test_03_replace,
    test_04_remove,
    test_05_capacity_limit,
    test_06_frozen_snapshot_immutable,
    test_07_disk_persistence,
    test_08_format_for_prompt_structure,
    test_09_user_store_independent,
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
    print("Test 02: Semantic Memory Store 검증")
    print("=" * 70)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['test']}: {r['detail']}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n  Result: {passed}/{total} passed")
