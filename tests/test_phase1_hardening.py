"""
Phase 1 Hardening Verification Suite (Tasks 1–6)
================================================
1. Task 1: Multi-user & Multi-session state isolation (plan/task tools, SemanticMemory, EpisodicStore)
2. Task 2: Unified thread_locks preventing Double-Texting & Reactive Wakeup race conditions
3. Task 3: SQLite WAL mode, non-blocking async CRUD (aiosqlite), shared AsyncSqliteSaver checkpointer, and thread_links deletion
4. Task 4: AsyncAgentClient connection pooling, unified SSE generator (_stream_agent_events), and background memory review cancellation
5. Task 5: Double-Texting error SSE event & inflight counter verification
6. Task 6: Unified user -> session -> subagent workspace hierarchy & 403 /artifacts guard
"""

import asyncio
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestPhase1Hardening(unittest.IsolatedAsyncioTestCase):
    """Phase 1 (Tasks 1~6) 통합 검증 테스트."""

    async def test_task1_plan_and_task_session_isolation(self):
        """[Task 1] 두 세션(session_alpha, session_beta)이 동시에 plan/task 도구를 사용할 때 상태가 완벽히 격리되는지 검증."""
        from app.tools.plan import (
            enter_plan,
            exit_plan,
            task_create,
            task_list,
            task_update,
            plan_session_scope,
            get_plan_state,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.tools.plan.PLANS_BASE_DIR", Path(tmpdir)):
                # 세션 Alpha에서 플랜 및 태스크 생성
                with plan_session_scope("session_alpha"):
                    res_a = enter_plan.invoke({"plan_name": "Alpha Goal", "steps": ["Step A1", "Step A2"]})
                    self.assertIn("Alpha Goal", res_a)
                    t_a = task_create.invoke({"task_description": "Scrape Alpha"})
                    self.assertIn("Task #1", t_a)

                # 세션 Beta에서 플랜 및 태스크 생성
                with plan_session_scope("session_beta"):
                    res_b = enter_plan.invoke({"plan_name": "Beta Goal", "steps": ["Step B1"]})
                    self.assertIn("Beta Goal", res_b)
                    t_b = task_create.invoke({"task_description": "Analyze Beta"})
                    self.assertIn("Task #1", t_b)
                    task_update.invoke({"task_id": 1, "status": "COMPLETED"})

                # Alpha 상태가 Beta에 의해 덮어써지지 않았는지 확인
                with plan_session_scope("session_alpha"):
                    list_a = task_list.invoke({})
                    self.assertIn("Scrape Alpha", list_a)
                    self.assertIn("PENDING", list_a)
                    self.assertNotIn("Analyze Beta", list_a)
                    state_a = get_plan_state("session_alpha")
                    self.assertEqual(state_a["plan_name"], "Alpha Goal")
                    self.assertTrue(state_a["active"])

                # Beta 상태 확인
                with plan_session_scope("session_beta"):
                    list_b = task_list.invoke({})
                    self.assertIn("Analyze Beta", list_b)
                    self.assertIn("COMPLETED", list_b)
                    self.assertNotIn("Scrape Alpha", list_b)
                    state_b = get_plan_state("session_beta")
                    self.assertEqual(state_b["plan_name"], "Beta Goal")
                    exit_plan.invoke({"plan_name": "Beta Goal", "status": "COMPLETED"})

                # 세션별 파일 경로가 물리적으로 분리되어 있는지 확인
                self.assertTrue(os.path.exists(os.path.join(tmpdir, "session_alpha", "plan_state.json")))
                self.assertTrue(os.path.exists(os.path.join(tmpdir, "session_alpha", "task_state.json")))
                self.assertTrue(os.path.exists(os.path.join(tmpdir, "session_beta", "plan_state.json")))
                self.assertTrue(os.path.exists(os.path.join(tmpdir, "session_beta", "task_state.json")))

    async def test_task1_multi_user_memory_isolation(self):
        """[Task 1] 사용자별 SemanticMemoryStore(USER.md/MEMORY.md) 및 EpisodicStore(user_id)가 격리되는지 검증."""
        from app.middleware.memory.episodic_store import EpisodicStore
        from app.middleware.memory.memory_middleware import MemoryMiddleware
        from app.middleware.memory.semantic_store import SemanticMemoryStore
        from langchain_core.messages import HumanMessage, AIMessage

        with tempfile.TemporaryDirectory() as tmpdir:
            sem_root = os.path.join(tmpdir, "semantic")
            epi_db = os.path.join(tmpdir, "episodic.db")

            base_sem = SemanticMemoryStore(memory_dir=sem_root)
            epi = EpisodicStore(db_path=epi_db)
            mw = MemoryMiddleware(semantic_store=base_sem, episodic_store=epi)
            try:
                # User Alice와 User Bob의 Semantic Store 분리 확인
                store_alice = mw._get_semantic_store("alice")
                store_bob = mw._get_semantic_store("bob")
                self.assertNotEqual(store_alice.memory_dir, store_bob.memory_dir)

                store_alice.add("user", "Name: Alice (Quant Trader)")
                store_bob.add("user", "Name: Bob (Backend Engineer)")

                self.assertIn("Name: Alice (Quant Trader)", store_alice.user_entries)
                self.assertNotIn("Name: Bob (Backend Engineer)", store_alice.user_entries)
                self.assertIn("Name: Bob (Backend Engineer)", store_bob.user_entries)
                self.assertNotIn("Name: Alice (Quant Trader)", store_bob.user_entries)

                # EpisodicStore 사용자별 저장 및 검색 격리 확인
                await epi.finalize_session(
                    "sess_alice_1",
                    [HumanMessage(content="포트폴리오 리밸런싱 전략 알려줘"), AIMessage(content="앨리스 전용 비공개 리밸런싱 전략입니다.")],
                    user_id="alice",
                )
                await epi.finalize_session(
                    "sess_bob_1",
                    [HumanMessage(content="포트폴리오 쿠버네티스 배포 전략 알려줘"), AIMessage(content="밥 전용 쿠버네티스 배포 전략입니다.")],
                    user_id="bob",
                )

                alice_hits = await epi.search_sessions("포트폴리오", user_id="alice")
                bob_hits = await epi.search_sessions("포트폴리오", user_id="bob")

                self.assertEqual(len(alice_hits), 1)
                self.assertEqual(alice_hits[0]["session_id"], "sess_alice_1")
                self.assertEqual(len(bob_hits), 1)
                self.assertEqual(bob_hits[0]["session_id"], "sess_bob_1")

                # [보강 1] Negative Test: bob이 alice의 session_id로 session_recall 도구를 호출해도 조회가 차단되는지 검증
                from app.middleware.memory.memory_middleware import _memory_user_id_var
                recall_tool = mw._create_session_recall_tool()
                tok_bob = _memory_user_id_var.set("bob")
                try:
                    bob_recall_alice = await recall_tool.coroutine(session_id="sess_alice_1")
                finally:
                    _memory_user_id_var.reset(tok_bob)
                self.assertIn("No messages found", bob_recall_alice)
                self.assertNotIn("앨리스 전용 비공개", bob_recall_alice)

                # alice 본인이 호출하면 정상 조회됨
                tok_alice = _memory_user_id_var.set("alice")
                try:
                    alice_recall_own = await recall_tool.coroutine(session_id="sess_alice_1")
                finally:
                    _memory_user_id_var.reset(tok_alice)
                self.assertIn("앨리스 전용 비공개 리밸런싱 전략입니다.", alice_recall_own)

                # [보강 1-2] abefore_agent가 _run_async_safe(스레드 블로킹)를 거치지 않고 네이티브 비동기로 동작하는지 검증
                from types import SimpleNamespace
                import app.middleware.memory.memory_middleware as mm_mod
                fake_runtime = SimpleNamespace(
                    context=SimpleNamespace(
                        user_id="alice",
                        recalled_memory="",
                        semantic_memory_enabled=True,
                        semantic_learning_enabled=True,
                        episodic_memory_enabled=True,
                        episodic_learning_enabled=True,
                    ),
                    execution_info=SimpleNamespace(thread_id="sess_alice_2"),
                )
                with patch.object(mm_mod, "_run_async_safe", side_effect=AssertionError("_run_async_safe should not be called in abefore_agent")):
                    await mw.abefore_agent(
                        {"messages": [HumanMessage(content="포트폴리오 리밸런싱")]},
                        fake_runtime,
                    )
                    self.assertIn("sess_alice_1", fake_runtime.context.recalled_memory)
            finally:
                await epi.close()

    async def test_task2_unified_thread_locks_prevent_race(self):
        """[Task 2] 동일 thread_id에 대해 /stream 동시 요청 시 queued SSE 이벤트가 선발송되고 직렬화(Serialization)되는지 검증."""
        import json
        from types import SimpleNamespace
        import httpx
        from langchain_core.messages import AIMessageChunk
        import app.server as server_mod

        tid = "race_test_thread"
        lock_from_stream = server_mod.get_thread_lock(tid)
        lock_from_wakeup = server_mod.wakeup_locks.get(tid)
        self.assertIs(lock_from_stream, lock_from_wakeup)

        execution_order = []
        first_entered = asyncio.Event()

        class FakeStreamingExecutor:
            async def astream_events(self, stream_input, config=None, context=None, version="v2"):
                msg = stream_input["messages"][0][1]
                execution_order.append(f"{msg}_start")
                if msg == "req1":
                    first_entered.set()
                    for _ in range(100):
                        if server_mod.thread_inflight_counts.get(tid, 0) >= 2:
                            break
                        await asyncio.sleep(0.01)
                else:
                    await asyncio.sleep(0.01)
                yield {
                    "event": "on_chat_model_stream",
                    "tags": [],
                    "data": {"chunk": AIMessageChunk(content=f"ack:{msg}")},
                }
                execution_order.append(f"{msg}_end")

            async def aget_state(self, config):
                return SimpleNamespace(tasks=[], values={"messages": []})

        with patch.object(server_mod, "get_or_load_agent", return_value=FakeStreamingExecutor()):
            transport = httpx.ASGITransport(app=server_mod.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
                async def call_stream(msg: str):
                    if msg == "req2":
                        await first_entered.wait()
                    resp = await ac.post(
                        "/agents/main_agent/stream",
                        json={"message": msg, "thread_id": tid, "user_id": "alice"},
                    )
                    self.assertEqual(resp.status_code, 200)
                    events = []
                    for line in resp.text.splitlines():
                        if line.startswith("data: ") and line[6:].strip():
                            events.append(json.loads(line[6:]))
                    return events

                events1, events2 = await asyncio.gather(
                    call_stream("req1"),
                    call_stream("req2"),
                )

        # 1. 인터리빙 없이 req1이 완전히 끝난 뒤 req2가 시작되어야 함
        self.assertEqual(
            execution_order,
            ["req1_start", "req1_end", "req2_start", "req2_end"],
        )
        # 2. 뒤따라온 req2의 첫 SSE 이벤트는 {"type": "queued", "thread_id": tid} 여야 함
        self.assertGreaterEqual(len(events2), 2)
        self.assertEqual(events2[0], {"type": "queued", "thread_id": tid})
        self.assertEqual(events2[1], {"type": "token", "content": "ack:req2"})

    async def test_task3_wal_mode_async_crud_and_shared_checkpointer(self):
        """[Task 3] checkpoints.db 단일 DB 통합(SSOT), SQLite WAL 모드, 비동기 CRUD(aiosqlite), Checkpointer 기반 get_messages/delete_session 검증."""
        import app.utils.database.session_store as ss
        from langchain.agents import create_agent
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage

        # 기본 설정에서 DB_PATH와 CHECKPOINTS_DB_PATH가 동일한 checkpoints.db를 가리키는지 검증
        self.assertEqual(ss.DB_PATH, ss.CHECKPOINTS_DB_PATH)
        self.assertTrue(ss.CHECKPOINTS_DB_PATH.endswith("checkpoints.db"))

        with tempfile.TemporaryDirectory() as tmpdir:
            test_cp_db = os.path.join(tmpdir, "checkpoints.db")

            with patch.object(ss, "DB_PATH", test_cp_db), \
                 patch.object(ss, "CHECKPOINTS_DB_PATH", test_cp_db):

                ss.init_db(force=True)

                # WAL 모드 활성화 확인
                conn = sqlite3.connect(test_cp_db)
                mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
                conn.close()
                self.assertEqual(mode.lower(), "wal")

                # 비동기 세션 생성 및 user_id 필터링 검증
                s1_initial = await ss.create_session("s_u1", "main_agent", "User 1 Chat", user_id="user_1")
                await ss.create_session("s_u2", "main_agent", "User 2 Chat", user_id="user_2")

                # [보강 2] 동일 session_id로 재생성 시 created_at과 최초 user_id가 덮어써지지 않고 title만 갱신되는지 검증
                await asyncio.sleep(0.01)
                s1_recreated = await ss.create_session("s_u1", "main_agent", "Renamed Title", user_id="user_2")
                self.assertEqual(s1_recreated["created_at"], s1_initial["created_at"])
                self.assertEqual(s1_recreated["user_id"], "user_1")
                self.assertEqual(s1_recreated["title"], "Renamed Title")

                u1_sessions = await ss.get_sessions("main_agent", user_id="user_1")
                u2_sessions = await ss.get_sessions("main_agent", user_id="user_2")
                self.assertEqual(len(u1_sessions), 1)
                self.assertEqual(u1_sessions[0]["session_id"], "s_u1")
                self.assertEqual(u1_sessions[0]["title"], "Renamed Title")
                self.assertEqual(len(u2_sessions), 1)
                self.assertEqual(u2_sessions[0]["session_id"], "s_u2")

                # 공유 Checkpointer 싱글톤 및 Checkpointer SSOT 기반 get_messages 검증
                await ss.close_shared_checkpointer()
                cp1 = await ss.get_shared_checkpointer()
                cp2 = await ss.get_shared_checkpointer()
                self.assertIs(cp1, cp2)

                fake_agent = create_agent(
                    model=GenericFakeChatModel(
                        messages=iter([
                            AIMessage(content="Hi async from checkpointer"),
                            AIMessage(content="Wakeup synthesized reply"),
                            AIMessage(content="Subagent finished"),
                            AIMessage(content="Reply in chat_old"),
                        ])
                    ),
                    tools=[],
                    system_prompt="You are a test agent.",
                    checkpointer=cp1,
                )
                await fake_agent.ainvoke(
                    {"messages": [("user", "Hello async")]},
                    config={"configurable": {"thread_id": "s_u1"}},
                )
                # 내부 Reactive Wakeup 알림은 get_messages에서 제외되고 최종 AI 답변만 노출되어야 함
                await fake_agent.ainvoke(
                    {"messages": [("user", "[SYSTEM NOTIFICATION: BACKGROUND TASK COMPLETED]\n- Job ID: job_1")]},
                    config={"configurable": {"thread_id": "s_u1"}},
                )
                # 하위 서브에이전트 체크포인트 생성 + 명시적 thread_links 등록
                await ss.register_subagent_thread("s_u1_scraper_1234abcd", "s_u1")
                await fake_agent.ainvoke(
                    {"messages": [("user", "Subagent task")]},
                    config={"configurable": {"thread_id": "s_u1_scraper_1234abcd"}},
                )
                # 접두사(s_u1_)가 겹치지만 별개 메인 세션인 s_u1_old 생성 (delete_session("s_u1") 시 보존되어야 함!)
                await ss.create_session("s_u1_old", "main_agent", "Old Sibling Session", user_id="user_1")
                await fake_agent.ainvoke(
                    {"messages": [("user", "Question in s_u1_old")]},
                    config={"configurable": {"thread_id": "s_u1_old"}},
                )

                self.assertEqual(len(await ss.get_messages("s_u1_scraper_1234abcd")), 2)
                self.assertEqual(len(await ss.get_messages("s_u1_old")), 2)

                msgs = await ss.get_messages("s_u1")
                self.assertEqual(
                    msgs,
                    [
                        {"role": "user", "content": "Hello async"},
                        {"role": "assistant", "content": "Hi async from checkpointer"},
                        {"role": "assistant", "content": "Wakeup synthesized reply"},
                    ],
                )

                # delete_session("s_u1") 호출 시:
                # - s_u1 메타데이터/체크포인트 삭제
                # - 명시적으로 링크된 자식 서브에이전트(s_u1_scraper_1234abcd) 체크포인트 삭제
                # - 접두사만 겹치는 다른 메인 세션(s_u1_old)은 절대 삭제되지 않고 100% 보존됨을 검증!
                await ss.delete_session("s_u1")
                self.assertIsNone(await ss.get_session("s_u1"))
                self.assertEqual(await ss.get_messages("s_u1"), [])
                self.assertEqual(await ss.get_messages("s_u1_scraper_1234abcd"), [])

                self.assertIsNotNone(await ss.get_session("s_u1_old"))
                self.assertEqual(
                    await ss.get_messages("s_u1_old"),
                    [
                        {"role": "user", "content": "Question in s_u1_old"},
                        {"role": "assistant", "content": "Reply in chat_old"},
                    ],
                )

                await ss.close_shared_checkpointer()

    async def test_task4_client_pool_and_background_review_cancellation(self):
        """[Task 4] AsyncAgentClient 커넥션 풀 재사용 및 취소된 백그라운드 리뷰가 파일/DB에 쓰지 않는지 검증."""
        from app.client import AsyncAgentClient
        from app.middleware.memory.episodic_store import EpisodicStore
        from app.middleware.memory.memory_middleware import MemoryMiddleware
        from app.middleware.memory.semantic_store import SemanticMemoryStore

        # 1. AsyncAgentClient 커넥션 풀 재사용 확인
        client = AsyncAgentClient(base_url="http://localhost:8000")
        http_c1 = client._get_client()
        http_c2 = client._get_client()
        self.assertIs(http_c1, http_c2)
        await client.aclose()
        self.assertTrue(http_c1.is_closed)

        # 2. [보강 3] 취소된 백그라운드 리뷰(cancel_event.set())가 USER.md/MEMORY.md나 Episodic DB에 쓰지 않는지 검증
        with tempfile.TemporaryDirectory() as tmpdir:
            sem = SemanticMemoryStore(memory_dir=os.path.join(tmpdir, "sem"))
            epi = EpisodicStore(db_path=os.path.join(tmpdir, "epi.db"))
            mw = MemoryMiddleware(semantic_store=sem, episodic_store=epi)
            try:
                cancel_ev = threading.Event()
                with mw._review_meta_lock:
                    mw._review_cancel_events["sess_cancel_test"] = cancel_ev

                # 새 턴 진입으로 인해 기존 백그라운드 리뷰 취소 시그널 발생
                mw._cancel_active_review("sess_cancel_test")
                self.assertTrue(cancel_ev.is_set())

                # 취소된 이벤트로 _background_review가 실행되더라도 LLM 호출이나 파일/DB 기록 없이 즉시 종료되어야 함
                test_msgs = [
                    {"role": "human", "content": "내 이름은 홍길동이고 파이썬을 좋아해"},
                    {"role": "ai", "content": "반갑습니다 홍길동님!"},
                    {"role": "human", "content": "기억해줘"},
                    {"role": "ai", "content": "네 기억하겠습니다."},
                ]
                with patch.object(mw, "_review_semantic_memory", side_effect=AssertionError("Semantic review should not run when cancelled")), \
                     patch.object(mw, "_review_episodic_memory", side_effect=AssertionError("Episodic review should not run when cancelled")):
                    mw._background_review(
                        test_msgs,
                        "sess_cancel_test",
                        user_id="alice",
                        semantic_learning=True,
                        episodic_learning=True,
                        cancel_event=cancel_ev,
                    )

                alice_sem = mw._get_semantic_store("alice")
                self.assertEqual(alice_sem.user_entries, [])
                self.assertEqual(alice_sem.memory_entries, [])
                alice_epi = await epi.browse_recent(limit=10, user_id="alice")
                self.assertEqual(alice_epi, [])
            finally:
                await epi.close()

    async def test_task5_double_texting_error_event_and_inflight_counter(self):
        """[Double-Texting 보강] SSE 오류 이벤트에 type='error'가 포함되는지 및 thread_inflight_counts 카운터가 정확히 동작하는지 검증."""
        import json
        import httpx
        import app.server as server_mod

        tid = "error_and_counter_thread"
        self.assertEqual(server_mod.thread_inflight_counts.get(tid, 0), 0)

        first_holding = asyncio.Event()
        release_first = asyncio.Event()

        async def holder_1():
            async with server_mod.acquire_thread_slot(tid):
                first_holding.set()
                await release_first.wait()

        task1 = asyncio.create_task(holder_1())
        await first_holding.wait()
        self.assertEqual(server_mod.thread_inflight_counts.get(tid, 0), 1)

        async def waiter():
            async with server_mod.acquire_thread_slot(tid):
                pass

        task2 = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)
        self.assertEqual(server_mod.thread_inflight_counts.get(tid, 0), 2)

        release_first.set()
        await asyncio.gather(task1, task2)
        self.assertEqual(server_mod.thread_inflight_counts.get(tid, 0), 0)

        # 2. 스트리밍 도중 예외 발생 시 SSE 페이로드에 {"type": "error", "error": "..."} 가 반환되는지 검증
        class FailingExecutor:
            async def astream_events(self, stream_input, config=None, context=None, version="v2"):
                raise RuntimeError("Simulated LLM stream failure")
                yield  # pragma: no cover

        with patch.object(server_mod, "get_or_load_agent", return_value=FailingExecutor()):
            transport = httpx.ASGITransport(app=server_mod.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
                resp = await ac.post(
                    "/agents/main_agent/stream",
                    json={"message": "trigger error", "thread_id": tid, "user_id": "alice"},
                )
                self.assertEqual(resp.status_code, 200)
                events = [
                    json.loads(line[6:])
                    for line in resp.text.splitlines()
                    if line.startswith("data: ") and line[6:].strip()
                ]
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["type"], "error")
                self.assertIn("Simulated LLM stream failure", events[0]["error"])

    async def test_task6_unified_user_session_subagent_workspace_hierarchy(self):
        """[Unified Workspace] user_id -> session_id -> subagents/{role}_{id} 계층형 디렉터리 및 Layer 3 프롬프트 주입 검증."""
        from types import SimpleNamespace
        from langchain_core.messages import HumanMessage
        import app.utils.workspace as ws_mod
        from app.tools.plan import enter_plan, plan_session_scope
        from app.middleware.observability.agent_log_tracer import AgentLogTracer
        from app.middleware.prompt.prompt_assembler import PromptAssembler, PromptAssemblerMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            users_root = Path(tmpdir) / "users"
            with patch.object(ws_mod, "USERS_ROOT_DIR", users_root), patch.object(ws_mod, "USERS_BASE_DIR", users_root):
                # 0. Path Traversal 세그먼트(".", "..") 차단 검증
                self.assertEqual(ws_mod.sanitize_path_segment(".."), "default")
                self.assertEqual(ws_mod.sanitize_path_segment("."), "default")
                self.assertEqual(ws_mod.sanitize_path_segment("..."), "default")

                # 1. 메인 에이전트 세션 워크스페이스 해석 검증 & 과거 정규식 오탐 케이스(session_job_1a2b3c4d, my_test_20261018)가
                #    parent_session_id 없이는 절대 서브에이전트로 오판되지 않음을 검증
                for main_tid in ("sess_2026_main", "session_job_1a2b3c4d", "my_test_20261018"):
                    m_ws = ws_mod.resolve_session_workspace(
                        user_id="alice",
                        session_id=main_tid,
                        ensure_exists=True,
                    )
                    self.assertFalse(m_ws.is_subagent, f"{main_tid} should not be guessed as subagent")
                    self.assertEqual(m_ws.root_dir, users_root / "alice" / "sessions" / main_tid)

                main_ws = ws_mod.resolve_session_workspace(
                    user_id="alice",
                    session_id="sess_2026_main",
                    ensure_exists=True,
                )
                self.assertTrue(main_ws.plan_dir.is_dir())
                self.assertTrue(main_ws.logs_dir.is_dir())
                self.assertTrue(main_ws.scripts_dir.is_dir())
                self.assertTrue(main_ws.outputs_dir.is_dir())

                # 2. 명시적 parent_session_id 전달 시(역할명에 '_'가 포함된 data_analyst 포함)
                #    하위 subagents/{role}_{id}/ 중첩이 정확히 이루어지는지 검증
                sub_tid = "sess_2026_main_data_analyst_a1b2c3d4"
                sub_ws = ws_mod.resolve_session_workspace(
                    user_id="alice",
                    session_id=sub_tid,
                    parent_session_id="sess_2026_main",
                    subagent_role="data_analyst",
                    ensure_exists=True,
                )
                self.assertTrue(sub_ws.is_subagent)
                self.assertEqual(sub_ws.root_session_id, "sess_2026_main")
                self.assertEqual(sub_ws.parent_session_id, "sess_2026_main")
                self.assertEqual(
                    sub_ws.root_dir,
                    users_root / "alice" / "sessions" / "sess_2026_main" / "subagents" / "data_analyst_a1b2c3d4",
                )
                self.assertTrue(sub_ws.plan_dir.is_dir())
                self.assertTrue(sub_ws.logs_dir.is_dir())
                self.assertTrue(sub_ws.scripts_dir.is_dir())
                self.assertTrue(sub_ws.outputs_dir.is_dir())

                # 3. plan 도구가 메인/서브에이전트 각각의 plan/ 디렉터리에 저장되는지 검증
                with plan_session_scope("sess_2026_main", user_id="alice"):
                    enter_plan.invoke({"plan_name": "Main Plan", "steps": ["Step 1"]})
                self.assertTrue((main_ws.plan_dir / "plan_state.json").is_file())

                with plan_session_scope(sub_tid, user_id="alice", parent_session_id="sess_2026_main"):
                    enter_plan.invoke({"plan_name": "Sub Plan", "steps": ["Sub Step 1"]})
                self.assertTrue((sub_ws.plan_dir / "plan_state.json").is_file())

                # 4. AgentLogTracer가 메인/서브에이전트 각각의 logs/audit.jsonl 경로를 해석하는지 검증
                tracer = AgentLogTracer(log_dir="./artifacts/users")
                main_log_file = tracer._resolve_target_file("sess_2026_main", user_id="alice")
                sub_log_file = tracer._resolve_target_file(
                    sub_tid, user_id="alice", parent_session_id="sess_2026_main"
                )
                self.assertEqual(Path(main_log_file), main_ws.logs_dir / "audit.jsonl")
                self.assertEqual(Path(sub_log_file), sub_ws.logs_dir / "audit.jsonl")

                # 5. PromptAssemblerMiddleware가 ctx.workspace_dir(SSOT) 또는 parent_session_id를 통해
                #    Layer 3에 Session Workspace 경로(Plan/Scripts/Outputs/Logs Dir)를 주입하는지 검증
                assembler = PromptAssembler(system_rules="Test system rules")
                pa_mw = PromptAssemblerMiddleware(assembler, merge_system=True)
                fake_request = SimpleNamespace(
                    runtime=SimpleNamespace(
                        context=SimpleNamespace(
                            cwd="/workspace",
                            session_id=sub_tid,
                            user_id="alice",
                            parent_session_id="sess_2026_main",
                            user_permission="USER",
                            active_project="harness_agent",
                            recalled_memory="",
                            workspace_dir=sub_ws.rel_root,
                        ),
                        config={
                            "configurable": {
                                "thread_id": sub_tid,
                                "user_id": "alice",
                                "parent_thread_id": "sess_2026_main",
                            }
                        },
                        execution_info=SimpleNamespace(thread_id=sub_tid),
                    ),
                    tools=[],
                    messages=[HumanMessage(content="분석 시작해줘")],
                )
                prepared_msgs = pa_mw._prepare_messages(fake_request)
                sys_prompt_text = prepared_msgs[0].content
                self.assertIn("Session Workspace Root:", sys_prompt_text)
                self.assertIn("subagents/data_analyst_a1b2c3d4", sys_prompt_text)
                self.assertIn("Plan Dir", sys_prompt_text)
                self.assertIn("Scripts Dir", sys_prompt_text)
                self.assertIn("Outputs Dir", sys_prompt_text)

                # 6. invoke_sub_agent 위임 헤더에 Sub-Agent Dedicated Workspace 경로가 실제로 포함되고
                #    parent_thread_id가 클라이언트로 전달되는지 검증 (회귀 방지)
                from app.tools import supervisor_tools

                captured_call = {}

                class _FakeClient:
                    async def get_agents(self):
                        return [{"name": "data_analyst"}]

                    async def async_invoke(self, **kwargs):
                        captured_call.update(kwargs)
                        return {"content": "Subagent finished"}

                fake_runtime = SimpleNamespace(
                    execution_info=SimpleNamespace(thread_id="sess_2026_main"),
                    context=SimpleNamespace(user_id="alice", session_id="sess_2026_main", agent_name="main_agent"),
                    config={"configurable": {"thread_id": "sess_2026_main", "user_id": "alice"}},
                )
                with patch.object(supervisor_tools, "get_subagent_client", return_value=_FakeClient()):
                    res = await supervisor_tools.invoke_sub_agent.coroutine(
                        task_instruction="매출 데이터 요약해줘",
                        subagent_role="data_analyst",
                        run_in_background=False,
                        runtime=fake_runtime,
                    )
                self.assertIn("Sub-Agent Dedicated Workspace:", captured_call.get("message", ""))
                self.assertIn("subagents/data_analyst_", captured_call.get("message", ""))
                self.assertEqual(captured_call.get("parent_thread_id"), "sess_2026_main")
                self.assertEqual(captured_call.get("user_id"), "alice")
                self.assertIn("Subagent finished", res)

                # 7. 해결안 A: /artifacts 정적 서빙에서 memory/, logs/, plan/, .db, .jsonl 접근 시 403 차단 검증
                import httpx
                from app.server import app

                mem_dir = ws_mod.resolve_user_memory_dir("alice", ensure_exists=True)
                (mem_dir / "USER.md").write_text("secret profile", encoding="utf-8")
                (main_ws.logs_dir / "audit.jsonl").write_text("{}", encoding="utf-8")

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    r_mem = await client.get("/artifacts/users/alice/memory/USER.md")
                    r_log = await client.get("/artifacts/users/alice/sessions/sess_2026_main/logs/audit.jsonl")
                    r_db = await client.get("/artifacts/users/alice/memory/episodic.db")
                    self.assertEqual(r_mem.status_code, 403)
                    self.assertEqual(r_log.status_code, 403)
                    self.assertEqual(r_db.status_code, 403)

    async def test_task5_dual_mode_agent_packages_and_prompt_assembler(self):
        """[Task 5] 단일 모듈(chatbot) 및 패키지 구조(main_agent, scraper, analyst) 듀얼 로더 & 내재화 스킬 PromptAssembler 검증."""
        from app.server import app, api_list_agents, get_or_load_agent, _find_agent_module_path
        from app.utils.context import AgentContext

        # 1. 듀얼 모듈 경로 탐색 확인 (패키지 vs 단일 파일)
        agents_dir = "app/agents"
        self.assertEqual(_find_agent_module_path("main_agent", agents_dir), "app.agents.main_agent.agent")
        self.assertEqual(_find_agent_module_path("scraper", agents_dir), "app.agents.scraper.agent")
        self.assertEqual(_find_agent_module_path("analyst", agents_dir), "app.agents.analyst.agent")
        self.assertEqual(_find_agent_module_path("chatbot", agents_dir), "app.agents.chatbot")

        # 2. /agents 엔드포인트 목록에 4개 에이전트 모두 노출 확인
        agents_resp = api_list_agents()
        agent_names = {a["name"] for a in agents_resp}
        self.assertTrue({"main_agent", "scraper", "analyst", "chatbot"}.issubset(agent_names))

        # 3. 각 패키지 에이전트 로드 및 PromptAssembler L2.2 스킬 카탈로그 + L3 워크스페이스 주입 확인
        from app.utils.database import close_shared_checkpointer
        ctx = {
            "session_id": "sess_pkg_test",
            "user_id": "alice",
            "workspace_dir": "artifacts/users/alice/sessions/sess_pkg_test",
        }
        loaded_execs = []
        try:
            main_exec = await get_or_load_agent("main_agent", app)
            loaded_execs.append(main_exec)
            main_prompt = main_exec.assembler.build_system_prompt(ctx)
            self.assertIn("pykrx-korean-market", main_prompt)
            self.assertIn("pdf-processing", main_prompt)
            self.assertIn("Session Workspace Root:", main_prompt)

            scraper_exec = await get_or_load_agent("scraper", app)
            loaded_execs.append(scraper_exec)
            scraper_prompt = scraper_exec.assembler.build_system_prompt(ctx)
            self.assertIn("anti_bot_stealth", scraper_prompt)
            self.assertIn("api_reverse_engineering", scraper_prompt)
            self.assertIn("Session Workspace Root:", scraper_prompt)

            analyst_exec = await get_or_load_agent("analyst", app)
            loaded_execs.append(analyst_exec)
            analyst_prompt = analyst_exec.assembler.build_system_prompt(ctx)
            self.assertIn("chart_patterns", analyst_prompt)
            self.assertIn("xlsx_guide", analyst_prompt)
            self.assertIn("Session Workspace Root:", analyst_prompt)
        finally:
            for ex in loaded_execs:
                conn = getattr(ex, "checkpointer_conn", None)
                if conn is not None:
                    await conn.close()
                epi = getattr(ex, "episodic_store", None)
                if epi is not None and hasattr(epi, "close"):
                    await epi.close()
            if hasattr(app.state, "agents"):
                app.state.agents.clear()
            await close_shared_checkpointer()


if __name__ == "__main__":
    unittest.main()

