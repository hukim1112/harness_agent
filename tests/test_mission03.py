"""
tests/test_mission03.py

🎯 Mission 03 자동화 검증 및 프롬프트 조립 시각화 스크립트
1. L3 Semantic Memory (USER.md / MEMORY.md) 엔트리 검증
2. L2 Episodic Memory FTS5 인덱싱 (finalize_session & session_search/session_recall 2-Stage Pull) 검증
3. main_agent 메모리 도구(memory, session_search, session_recall) 및 미들웨어 통합 확인
4. 정적 SystemMessage 순수성 + User Context(세션 동결) + 도구 루프 프리픽스 캐시 불변 검증
5. 🎨 show_prompt_map 기반 실물 시각화 렌더링

실행 방법:
  python tests/test_mission03.py
"""

import asyncio
import os
import sys
import time

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)


async def run_prompt_and_memory_test():
    print("=" * 80)
    print("🧪 [Mission 03] Simplified Prompt Assembler & Layered Memory 통합 검증 시작")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. L3 Semantic Memory Store 검증
    # -------------------------------------------------------------------------
    from app.middleware.memory import SemanticMemoryStore

    test_mem_dir = "artifacts/users/default/memory"
    os.makedirs(test_mem_dir, exist_ok=True)
    sem_store = SemanticMemoryStore(memory_dir=test_mem_dir)
    sem_store.load_from_disk()

    user_entries = sem_store.user_entries
    mem_entries = sem_store.memory_entries
    print(
        f"  ✅ Test 1 통과: Semantic Memory Store 로드 성공 "
        f"(USER 엔트리: {len(user_entries)}개, MEMORY 엔트리: {len(mem_entries)}개)"
    )

    # -------------------------------------------------------------------------
    # 2. L2 Episodic Memory Store & finalize_session 검증
    # -------------------------------------------------------------------------
    from app.middleware.memory import EpisodicStore

    test_epi_dir = "app/database"
    os.makedirs(test_epi_dir, exist_ok=True)
    test_epi_path = os.path.join(test_epi_dir, "test_episodic_verify.db")
    if os.path.exists(test_epi_path):
        try:
            os.remove(test_epi_path)
        except Exception:
            pass

    epi_store = EpisodicStore(db_path=test_epi_path)
    await epi_store.setup()

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
        llm=None,
    )
    assert len(summary) > 0, "❌ finalize_session 요약 생성 실패"

    search_results = await epi_store.search_sessions(query="Qdrant 벡터", top_k=2)
    assert len(search_results) > 0, "❌ FTS5 search_sessions 검색 실패"
    print(f"  ✅ Test 2 통과: Episodic Store FTS5 인덱싱 및 검색 확인 (검색 적중 세션: {search_results[0]['session_id']})")

    # -------------------------------------------------------------------------
    # 3. main_agent 하네스 결합 검증
    # -------------------------------------------------------------------------
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    from app.agents import main_agent
    from app.context import AgentContext
    from app.middleware.prompt import PromptAssemblerMiddleware, simulate_turn
    from app.utils.message_markers import (
        ORIGIN_USER_CONTEXT,
        message_origin,
    )
    from tests.agent_inspector import (
        close_agent_resources,
        extract_agent_tools,
        extract_prompt_assembler,
        find_agent_middleware,
    )

    try:
        agent = await main_agent.create_agent_executor()
    except Exception as e:
        print(f"❌ [FAIL] main_agent 생성 중 에러 발생: {e}")
        return False

    all_tools = extract_agent_tools(agent)
    tool_names = {getattr(t, "name", "") for t in all_tools}

    assert "memory" in tool_names, "❌ memory 도구가 에이전트에 등록되지 않았습니다. middleware에 MemoryMiddleware가 포함되었는지 확인하세요."
    assert "session_search" in tool_names, "❌ session_search 도구가 에이전트에 등록되지 않았습니다."
    assert "session_recall" in tool_names, "❌ session_recall 도구가 에이전트에 등록되지 않았습니다."
    from app.tools.custom_tools import CUSTOM_TOOLS
    assert "roll_dice" in tool_names, "❌ 필수 커스텀 도구(roll_dice)가 active_tools에 포함되지 않았습니다."
    missing_custom = [getattr(t, "name", "") for t in CUSTOM_TOOLS if getattr(t, "name", "") not in tool_names]
    assert not missing_custom, f"❌ CUSTOM_TOOLS 항목이 active_tools에 누락되었습니다: {missing_custom}"
    print(f"  ✅ Test 3 통과: main_agent 메모리(3종)·커스텀 도구 바인딩 확인 (총 {len(all_tools)}종 도구)")

    assembler = extract_prompt_assembler(agent)
    prompt_mw = find_agent_middleware(agent, PromptAssemblerMiddleware)
    assert assembler is not None and prompt_mw is not None, "❌ main_agent에 PromptAssemblerMiddleware가 탑재되지 않았습니다."

    static_prompt = assembler.build_static_prompt()
    assert "당신은 사용자의 모든 요청을" in static_prompt, "❌ 정적 SystemMessage에 SUPERVISOR_SYSTEM_PROMPT가 포함되지 않았습니다."
    for leak in ("Session ID:", "Working Directory", "Current Date:", "MEMORY.md", "pykrx-korean-market"):
        assert leak not in static_prompt, f"❌ 정적 SystemMessage에 동적/스킬 목록 정보('{leak}')가 혼입되었습니다."
    print("  ✅ Test 4 통과: 정적 SystemMessage 순수성(가변 정보 0%) 및 PromptAssemblerMiddleware 탑재 확인")

    # -------------------------------------------------------------------------
    # 4. 🎨 4단 요청 구조 조립 & 2단계 도구 호출 루프 프리픽스 캐시 불변 실물 시각화
    # -------------------------------------------------------------------------
    snapshot_text = "\n\n".join(
        p for p in (sem_store.format_for_prompt("memory"), sem_store.format_for_prompt("user")) if p
    ) or "- [Semantic Profile]: Standard User"

    ctx = AgentContext(
        user_id="default",
        session_id=sample_sid,
        memory_snapshot=snapshot_text,
    )
    state = {"messages": [HumanMessage(content="추천 엔진 백엔드 아키텍처 결정 사항 정리해줘.", id="m03_u1")]}

    print("\n🎨 [실물 시각화 1] Turn 1 조립 결과 (Tools + Static System + Frozen User Context)")
    out_t1 = simulate_turn(prompt_mw, state, "Mission 03 — Turn 1", tools=all_tools, context=ctx)

    assert isinstance(out_t1.messages[0], SystemMessage)
    assert out_t1.messages[0].additional_kwargs.get("cache_control") == {"type": "ephemeral"}
    assert message_origin(out_t1.messages[1]) == ORIGIN_USER_CONTEXT
    assert "# sessionContext" in out_t1.messages[1].content
    assert "# memorySnapshot" in out_t1.messages[1].content
    assert len(out_t1.messages) == 3

    # Turn 1-② / Turn 2: session_search 도구 호출 결과를 거친 뒤에도 앞단 [00]~[02] 프리픽스 100% 바이트 일치 검증
    state["messages"] += [
        AIMessage(
            content="",
            id="m03_a1_tc",
            tool_calls=[{"name": "session_search", "args": {"query": "Qdrant"}, "id": "m03_tc1"}],
        ),
        ToolMessage(
            content=f'{{"results": [{{"session_id": "{search_results[0]["session_id"]}"}}]}}',
            tool_call_id="m03_tc1",
            name="session_search",
            id="m03_t1",
        ),
        AIMessage(content="FastAPI + Qdrant 벡터 DB 조합으로 확정했습니다.", id="m03_a1"),
        HumanMessage(content="임베딩 모델은 뭐로 정했었지?", id="m03_u2"),
    ]
    print("\n🎨 [실물 시각화 2] Turn 2 조립 결과 (앞 [00]~[02] 프리픽스 100% 캐시 유지)")
    out_t2 = simulate_turn(
        prompt_mw,
        state,
        "Mission 03 — Turn 2",
        prev_messages=out_t1.messages,
        tools=all_tools,
        context=ctx,
    )
    assert all(out_t2.messages[i].content == out_t1.messages[i].content for i in range(len(out_t1.messages))), (
        "❌ Turn 2에서 앞단 프리픽스 메시지가 변경되었습니다."
    )
    print("  ✅ Test 5 통과: User Context 동결 · session_search 도구 루프 · Turn 1→2 프리픽스 100% 바이트 일치 확인")

    # 리소스 정리 및 임시 DB 파일 삭제
    await close_agent_resources(agent)
    await epi_store.close()
    for base in (test_epi_path, os.path.join(test_epi_dir, "test_episodic_verify_transcript.db")):
        for ext in ("", "-wal", "-shm"):
            p = base + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    print("\n🎉 [Mission 03] 모든 하네스(프롬프트 조립 + 계층형 메모리) 검증 100% 통과!")
    return True


if __name__ == "__main__":
    import traceback

    success = False
    try:
        success = asyncio.run(run_prompt_and_memory_test())
    except AssertionError as e:
        print(f"\n{e}")
    except Exception:
        traceback.print_exc()
    finally:
        for stem in ("test_episodic_verify.db", "test_episodic_verify_transcript.db"):
            for ext in ("", "-wal", "-shm"):
                p = os.path.join(project_root, "app", "database", stem + ext)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0 if success else 1)
