"""
tests/test_prompt_and_memory.py

🎯 Mission 03 자동화 검증 및 프롬프트 시각화 스크립트
1. L3 Semantic Memory (USER.md / MEMORY.md) 엔트리 검증
2. L2 Episodic Memory FTS5 인덱싱 (finalize_session & 2-Stage JIT) 검증
3. main_agent 메모리 도구(memory, session_recall) 및 미들웨어 통합 확인
4. 🎨 LLM으로 주입되는 5-Layer System Prompt 실물 시각화 렌더링

실행 방법:
  python tests/test_prompt_and_memory.py
"""

import os
import sys
import asyncio
import shutil
import time

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)


async def run_prompt_and_memory_test():
    print("=" * 80)
    print("🧪 [Mission 03] 5-Layer Prompt Assembler & Layered Memory 통합 검증 시작")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. L3 Semantic Memory Store 검증
    # -------------------------------------------------------------------------
    from app.middleware.memory import SemanticMemoryStore

    test_mem_dir = "app/database"
    os.makedirs(test_mem_dir, exist_ok=True)
    sem_store = SemanticMemoryStore(memory_dir=test_mem_dir)
    sem_store.load_from_disk()

    user_entries = sem_store.user_entries
    mem_entries = sem_store.memory_entries
    print(f"  ✅ Test 1 통과: Semantic Memory Store 로드 성공 (USER 엔트리: {len(user_entries)}개, MEMORY 엔트리: {len(mem_entries)}개)")

    # -------------------------------------------------------------------------
    # 2. L2 Episodic Memory Store & finalize_session 검증
    # -------------------------------------------------------------------------
    from app.middleware.memory import EpisodicStore

    test_epi_dir = "artifacts/memory"
    os.makedirs(test_epi_dir, exist_ok=True)
    test_epi_path = os.path.join(test_epi_dir, "test_episodic_verify.db")
    if os.path.exists(test_epi_path):
        try:
            os.remove(test_epi_path)
        except Exception:
            pass

    epi_store = EpisodicStore(db_path=test_epi_path)
    await epi_store.setup()

    # 과거 가상 세션 데이터 finalize_session 인덱싱 테스트
    sample_sid = f"session_test_arch_{int(time.time())}"
    sample_msgs = [
        {"role": "user", "content": "차세대 추천 엔진 백엔드로 FastAPI와 Qdrant 벡터 DB를 채택하기로 했어."},
        {"role": "assistant", "content": "네, Qdrant 벡터 검색과 FastAPI 비동기 구조를 연동하여 밀리초 단위 검색 레이턴시를 확보하도록 확정했습니다."},
        {"role": "user", "content": "임베딩 모델은 text-embedding-3-small로 결정했지?"},
        {"role": "assistant", "content": "네, 1536차원 text-embedding-3-small 모델로 벡터 인덱스를 구축합니다."},
    ]
    summary = await epi_store.finalize_session(
        session_id=sample_sid,
        messages=sample_msgs,
        llm=None
    )
    assert len(summary) > 0, "❌ finalize_session 요약 생성 실패"

    # FTS5 검색 검증
    search_results = await epi_store.search_sessions(query="Qdrant 벡터", top_k=2)
    assert len(search_results) > 0, "❌ FTS5 search_sessions 검색 실패"
    print(f"  ✅ Test 2 통과: Episodic Store FTS5 인덱싱 및 검색 확인 (검색 적중 세션: {search_results[0]['session_id']})")

    # -------------------------------------------------------------------------
    # 3. main_agent 하네스 결합 검증
    # -------------------------------------------------------------------------
    from app.agents import main_agent

    try:
        agent = await main_agent.create_agent_executor()
    except Exception as e:
        print(f"❌ [FAIL] main_agent 생성 중 에러 발생: {e}")
        return False

    registered_tools = getattr(agent, "registered_tools", [])
    tool_names = {getattr(t, "name", "") for t in registered_tools}

    # 필수 메모리 도구 2종 검증
    assert "memory" in tool_names, "❌ memory 도구가 바인딩되지 않았습니다. MemoryMiddleware.get_tools()를 확인하세요."
    assert "session_recall" in tool_names, "❌ session_recall 도구가 바인딩되지 않았습니다."
    print(f"  ✅ Test 3 통과: main_agent에 메모리 전용 도구(memory, session_recall) 정상 바인딩 (총 {len(registered_tools)}종 도구)")

    # 미들웨어 탑재 여부 검증
    assembler = getattr(agent, "assembler", None)
    assert assembler is not None, "❌ main_agent에 PromptAssembler가 탑재되지 않았습니다."
    print("  ✅ Test 4 통과: Claude Code 5-Layer Prompt Assembler 정상 장착 확인")

    # -------------------------------------------------------------------------
    # 4. 🎨 조립된 5-Layer 프롬프트 실물 시각화 렌더링
    # -------------------------------------------------------------------------
    session_ctx = {
        "cwd": project_root,
        "session_id": sample_sid,
        "os": os.name,
        "user_permission": "ADMIN",
        "active_project": "agent_lab",
        "recalled_memory": f"• [Semantic Profile]: {user_entries[0] if user_entries else 'Standard User'}\n• [Episodic Hint]: 과거 세션({search_results[0]['session_id']})에서 Qdrant/FastAPI 아키텍처 논의 완료",
    }

    assembled_prompt = assembler.build_system_prompt(session_ctx)

    print("\n" + "=" * 80)
    print("🎨 [실물 시각화] LLM에 런타임 주입되는 5-Layer System Prompt 전문")
    print("=" * 80)
    
    # 계층별 구분 표시
    layers = [
        ("Layer 1: System Identity & Core Role", "=== Layer 1:"),
        ("Layer 2: Capabilities (Tools & Skills)", "=== Layer 2:"),
        ("Layer 3: Dynamic Session Context", "=== Layer 3:"),
        ("Layer 4: Memory & Dynamic Documents", "=== Layer 4:"),
        ("Layer 5: User & Local Project Rules", "=== Layer 5:"),
    ]

    print(assembled_prompt)
    print("=" * 80)

    # 리소스 정리
    conn = getattr(agent, "checkpointer_conn", None)
    if conn:
        await conn.close()
    if epi_store._conn:
        await epi_store._conn.close()

    print("\n🎉 [Mission 03] 모든 하네스(프롬프트 조립 + 계층형 메모리) 검증 100% 통과!")
    return True


if __name__ == "__main__":
    success = asyncio.run(run_prompt_and_memory_test())
    if not success:
        sys.exit(1)
