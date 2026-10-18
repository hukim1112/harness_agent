import asyncio
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.tools.supervisor_tools import (
    _FULL_PROTOCOL_HEADER,
    _PROTOCOL_REMINDER,
    get_sub_agent_job_status,
    invoke_sub_agent,
)


def _make_runtime(thread_id: str = "sup_session_100", agent_name: str = "main_agent"):
    return SimpleNamespace(
        execution_info=SimpleNamespace(thread_id=thread_id),
        context=SimpleNamespace(agent_name=agent_name, subagent_options={}),
    )


class FakeAsyncAgentClient:
    """In-memory fake server client to verify thread_id isolation, protocol headers, and continuation."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 600.0):
        self.base_url = base_url
        self.timeout = timeout

    # Shared state across client instances
    sessions: dict[str, list[dict]] = {}
    jobs: dict[str, dict] = {}
    invocations: list[dict] = []
    job_counter: int = 0

    @classmethod
    def reset(cls):
        cls.sessions = {}
        cls.jobs = {}
        cls.invocations = []
        cls.job_counter = 0

    async def get_agents(self):
        return [
            {"name": "scraper", "description": "Scraper agent"},
            {"name": "analyst", "description": "Analyst agent"},
            {"name": "main_agent", "description": "Main supervisor agent"},
        ]

    async def get_messages(self, session_id: str):
        return list(self.sessions.get(session_id, []))

    async def async_invoke(
        self,
        agent_name: str,
        message: str,
        thread_id: str = None,
        options: dict = None,
        user_id: str = "default",
        parent_thread_id: str = None,
    ):
        self.invocations.append(
            {
                "mode": "sync",
                "agent_name": agent_name,
                "message": message,
                "thread_id": thread_id,
                "options": options,
                "user_id": user_id,
                "parent_thread_id": parent_thread_id,
            }
        )
        msgs = self.sessions.setdefault(thread_id, [])
        msgs.append({"role": "user", "content": message})
        reply = f"[TASK REPORT]\n- Status: SUCCESS\n- Turn Count: {len(msgs)}"
        msgs.append({"role": "assistant", "content": reply})
        return {"type": "ai", "content": reply}

    async def submit_job(
        self,
        agent_name: str,
        message: str,
        thread_id: str = None,
        callback_agent: str = "main_agent",
        callback_thread_id: str = None,
        options: dict = None,
        user_id: str = "default",
        parent_thread_id: str = None,
    ):
        FakeAsyncAgentClient.job_counter += 1
        job_id = f"job_test_{FakeAsyncAgentClient.job_counter:04d}"
        self.invocations.append(
            {
                "mode": "background",
                "job_id": job_id,
                "agent_name": agent_name,
                "message": message,
                "thread_id": thread_id,
                "callback_agent": callback_agent,
                "callback_thread_id": callback_thread_id,
                "options": options,
                "user_id": user_id,
                "parent_thread_id": parent_thread_id,
            }
        )
        msgs = self.sessions.setdefault(thread_id, [])
        msgs.append({"role": "user", "content": message})
        reply = f"[TASK REPORT]\n- Status: SUCCESS\n- Job: {job_id}"
        msgs.append({"role": "assistant", "content": reply})
        self.jobs[job_id] = {
            "job_id": job_id,
            "agent_name": agent_name,
            "sub_thread_id": thread_id,
            "status": "SUCCESS",
            "created_at": "2026-10-14T00:00:00Z",
            "completed_at": "2026-10-14T00:01:00Z",
            "result": reply,
        }
        return {"job_id": job_id, "status": "SUBMITTED", "agent_name": agent_name}

    async def get_job(self, job_id: str):
        return self.jobs.get(job_id, {"status": "error", "message": "not found"})


class SubAgentSessionIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeAsyncAgentClient.reset()

    @patch("app.tools.supervisor_tools.get_subagent_client", side_effect=lambda: FakeAsyncAgentClient())
    async def test_parallel_calls_generate_unique_sub_thread_ids_and_isolate_memory(self, _mock_client):
        """동일 부모 세션에서 동시에 여러 scraper를 호출할 때 각각 고유한 sub_thread_id가 발급되고 메모리가 격리되는지 검증."""
        runtime = _make_runtime(thread_id="sup_parallel_01")

        res1, res2 = await asyncio.gather(
            invoke_sub_agent.coroutine(
                task_instruction="Scrape site A",
                target_file_list=["artifacts/data/site_a.json"],
                subagent_role="scraper",
                run_in_background=True,
                runtime=runtime,
            ),
            invoke_sub_agent.coroutine(
                task_instruction="Scrape site B",
                target_file_list=["artifacts/data/site_b.json"],
                subagent_role="scraper",
                run_in_background=True,
                runtime=runtime,
            ),
        )

        # 1. 두 호출 모두 [JOB SUBMITTED] 및 Sub-Thread ID를 반환해야 함
        self.assertIn("[JOB SUBMITTED]", res1)
        self.assertIn("[JOB SUBMITTED]", res2)

        m1 = re.search(r"- Sub-Thread ID: ([^\s]+)", res1)
        m2 = re.search(r"- Sub-Thread ID: ([^\s]+)", res2)
        self.assertIsNotNone(m1)
        self.assertIsNotNone(m2)

        tid1 = m1.group(1)
        tid2 = m2.group(1)

        # 2. 두 sub_thread_id가 서로 달라야 하며 부모 thread_id와 role 접두사를 포함해야 함
        self.assertNotEqual(tid1, tid2)
        self.assertTrue(tid1.startswith("sup_parallel_01_scraper_"))
        self.assertTrue(tid2.startswith("sup_parallel_01_scraper_"))

        # 3. 두 호출 모두 첫 호출이므로 _FULL_PROTOCOL_HEADER가 주입되어야 함
        self.assertEqual(len(FakeAsyncAgentClient.invocations), 2)
        self.assertIn(_FULL_PROTOCOL_HEADER, FakeAsyncAgentClient.invocations[0]["message"])
        self.assertIn(_FULL_PROTOCOL_HEADER, FakeAsyncAgentClient.invocations[1]["message"])

        # 4. 세션 메모리가 서로 섞이지 않고 각각의 thread_id에 독립 저장되어야 함
        self.assertEqual(len(FakeAsyncAgentClient.sessions[tid1]), 2)  # user + assistant
        self.assertEqual(len(FakeAsyncAgentClient.sessions[tid2]), 2)  # user + assistant
        self.assertIn("Scrape site A", FakeAsyncAgentClient.sessions[tid1][0]["content"])
        self.assertNotIn("Scrape site B", FakeAsyncAgentClient.sessions[tid1][0]["content"])

    @patch("app.tools.supervisor_tools.get_subagent_client", side_effect=lambda: FakeAsyncAgentClient())
    async def test_continuation_with_sub_thread_id_reuses_session_and_injects_reminder(self, _mock_client):
        """반환된 sub_thread_id를 인자로 전달하여 재호출하면 동일 세션을 이어받고 _PROTOCOL_REMINDER가 주입되는지 검증."""
        runtime = _make_runtime(thread_id="sup_cont_01")

        # 1차 호출 (sub_thread_id 미지정 -> 자동 생성)
        first_res = await invoke_sub_agent.coroutine(
            task_instruction="Initial scrape of page 1",
            target_file_list=["artifacts/data/quotes_p1.json"],
            subagent_role="scraper",
            run_in_background=False,
            runtime=runtime,
        )
        m = re.search(r"- Sub-Thread ID: ([^\s]+)", first_res)
        self.assertIsNotNone(m)
        sub_tid = m.group(1)

        # 1차 호출은 _FULL_PROTOCOL_HEADER 사용
        self.assertIn(_FULL_PROTOCOL_HEADER, FakeAsyncAgentClient.invocations[0]["message"])

        # 2차 연속 호출 (반환받은 sub_thread_id 전달)
        second_res = await invoke_sub_agent.coroutine(
            task_instruction="Continue scraping page 2 using the same selectors",
            target_file_list=["artifacts/data/quotes_p2.json"],
            subagent_role="scraper",
            run_in_background=False,
            sub_thread_id=sub_tid,
            runtime=runtime,
        )

        # 2차 호출 결과도 동일한 sub_tid를 유지해야 함
        self.assertIn(f"- Sub-Thread ID: {sub_tid}", second_res)
        self.assertEqual(FakeAsyncAgentClient.invocations[1]["thread_id"], sub_tid)

        # 2차 호출은 기존 이력이 존재하므로 _PROTOCOL_REMINDER가 주입되어야 함
        self.assertIn(_PROTOCOL_REMINDER, FakeAsyncAgentClient.invocations[1]["message"])
        self.assertNotIn(_FULL_PROTOCOL_HEADER, FakeAsyncAgentClient.invocations[1]["message"])

        # 해당 sub_tid 세션에 1차 + 2차 대화(총 4개 메시지)가 누적되어 있어야 함
        self.assertEqual(len(FakeAsyncAgentClient.sessions[sub_tid]), 4)

    @patch("app.tools.supervisor_tools.get_subagent_client", side_effect=lambda: FakeAsyncAgentClient())
    async def test_job_status_includes_sub_thread_id(self, _mock_client):
        """get_sub_agent_job_status 조회 시에도 Sub-Thread ID가 포함되어 반환되는지 검증."""
        runtime = _make_runtime(thread_id="sup_job_01")
        submit_res = await invoke_sub_agent.coroutine(
            task_instruction="Analyze dataset",
            target_file_list=["artifacts/data/items.json"],
            subagent_role="analyst",
            run_in_background=True,
            runtime=runtime,
        )
        job_id = re.search(r"- Job ID: ([^\s]+)", submit_res).group(1)
        sub_tid = re.search(r"- Sub-Thread ID: ([^\s]+)", submit_res).group(1)

        status_res = await get_sub_agent_job_status.coroutine(job_id=job_id)
        self.assertIn(f"- Job ID: {job_id}", status_res)
        self.assertIn(f"- Sub-Thread ID: {sub_tid}", status_res)

    async def test_server_background_jobs_checkpointer_isolation_and_wakeup_serialization(self):
        """실제 AsyncSqliteSaver 체크포인터와 server._run_agent_job을 사용하여
        동시 백그라운드 실행 시 하위 에이전트 메모리 격리, 연속 호출 시 메모리 유지,
        그리고 부모 Reactive Wakeup 직렬화가 정상 동작하는지 검증."""
        import tempfile
        import aiosqlite
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from langchain.agents import create_agent
        import app.server as server_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test_checkpoints.db"
            conn = await aiosqlite.connect(db_path, check_same_thread=False)
            try:
                checkpointer = AsyncSqliteSaver(conn)
                await checkpointer.setup()

                class MemoryInspectModel(GenericFakeChatModel):
                    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                        human_texts = [
                            m.content for m in messages if getattr(m, "type", "") == "human"
                        ]
                        summary = " | ".join(
                            t.splitlines()[-1] for t in human_texts if t
                        )
                        from langchain_core.outputs import ChatGeneration, ChatResult
                        return ChatResult(
                            generations=[
                                ChatGeneration(
                                    message=AIMessage(
                                        content=f"[TASK REPORT]\n- Seen: {summary}"
                                    )
                                )
                            ]
                        )

                sub_executor = create_agent(
                    model=MemoryInspectModel(messages=iter([])),
                    tools=[],
                    system_prompt="You are a test sub-agent.",
                    checkpointer=checkpointer,
                )
                sup_executor = create_agent(
                    model=MemoryInspectModel(messages=iter([])),
                    tools=[],
                    system_prompt="You are a test supervisor.",
                    checkpointer=checkpointer,
                )

                fake_app = SimpleNamespace(
                    state=SimpleNamespace(
                        agents={"scraper": sub_executor, "main_agent": sup_executor},
                        load_lock=asyncio.Lock(),
                    )
                )

                sup_tid = "sup_real_cp_01"
                sub_tid_a = f"{sup_tid}_scraper_aaaa1111"
                sub_tid_b = f"{sup_tid}_scraper_bbbb2222"

                server_mod.job_store["job_a"] = {
                    "job_id": "job_a",
                    "agent_name": "scraper",
                    "sub_thread_id": sub_tid_a,
                    "status": "SUBMITTED",
                }
                server_mod.job_store["job_b"] = {
                    "job_id": "job_b",
                    "agent_name": "scraper",
                    "sub_thread_id": sub_tid_b,
                    "status": "SUBMITTED",
                }

                input_a = server_mod.JobSubmitInput(
                    message="Header\nInstruction: SECRET_SITE_ALPHA",
                    thread_id=sub_tid_a,
                    callback_agent="main_agent",
                    callback_thread_id=sup_tid,
                )
                input_b = server_mod.JobSubmitInput(
                    message="Header\nInstruction: SECRET_SITE_BETA",
                    thread_id=sub_tid_b,
                    callback_agent="main_agent",
                    callback_thread_id=sup_tid,
                )

                ctx_a, cfg_a = await server_mod._resolve_run("scraper", sub_tid_a, parent_thread_id=sup_tid)
                ctx_b, cfg_b = await server_mod._resolve_run("scraper", sub_tid_b, parent_thread_id=sup_tid)

                # 1. 두 백그라운드 잡 동시 실행
                await asyncio.gather(
                    server_mod._run_agent_job("job_a", "scraper", input_a, ctx_a, cfg_a, fake_app),
                    server_mod._run_agent_job("job_b", "scraper", input_b, ctx_b, cfg_b, fake_app),
                )

                self.assertEqual(server_mod.job_store["job_a"]["status"], "SUCCESS")
                self.assertEqual(server_mod.job_store["job_b"]["status"], "SUCCESS")

                # 2. Checkpointer 내 두 서브에이전트의 단기 메모리가 절대 섞이지 않았음을 검증
                state_a = await sub_executor.aget_state({"configurable": {"thread_id": sub_tid_a}})
                state_b = await sub_executor.aget_state({"configurable": {"thread_id": sub_tid_b}})

                msgs_a = [m.content for m in state_a.values["messages"]]
                msgs_b = [m.content for m in state_b.values["messages"]]

                self.assertEqual(len(msgs_a), 2)
                self.assertEqual(len(msgs_b), 2)
                self.assertTrue(any("SECRET_SITE_ALPHA" in c for c in msgs_a))
                self.assertFalse(any("SECRET_SITE_BETA" in c for c in msgs_a))
                self.assertTrue(any("SECRET_SITE_BETA" in c for c in msgs_b))
                self.assertFalse(any("SECRET_SITE_ALPHA" in c for c in msgs_b))

                # 3. sub_tid_a를 재사용하여 연속 작업(Follow-up) 실행 시 이전 기억(ALPHA)을 유지하는지 검증
                server_mod.job_store["job_a_followup"] = {
                    "job_id": "job_a_followup",
                    "agent_name": "scraper",
                    "sub_thread_id": sub_tid_a,
                    "status": "SUBMITTED",
                }
                input_a_followup = server_mod.JobSubmitInput(
                    message="Reminder\nInstruction: FOLLOWUP_ALPHA_PAGE_2",
                    thread_id=sub_tid_a,
                    callback_agent="main_agent",
                    callback_thread_id=sup_tid,
                )
                await server_mod._run_agent_job(
                    "job_a_followup", "scraper", input_a_followup, ctx_a, cfg_a, fake_app
                )

                state_a_after = await sub_executor.aget_state({"configurable": {"thread_id": sub_tid_a}})
                msgs_a_after = [m.content for m in state_a_after.values["messages"]]
                self.assertEqual(len(msgs_a_after), 4)
                self.assertIn("SECRET_SITE_ALPHA", msgs_a_after[-1])
                self.assertIn("FOLLOWUP_ALPHA_PAGE_2", msgs_a_after[-1])

                # 4. Supervisor의 Checkpointer에 Reactive Wakeup 알림(Sub-Thread ID 포함)이 정상 기록되었는지 검증
                sup_state = await sup_executor.aget_state({"configurable": {"thread_id": sup_tid}})
                sup_msgs = [m.content for m in sup_state.values["messages"]]
                self.assertEqual(len(sup_msgs), 6)
                self.assertTrue(any(f"- Sub-Thread ID: {sub_tid_a}" in c for c in sup_msgs))
                self.assertTrue(any(f"- Sub-Thread ID: {sub_tid_b}" in c for c in sup_msgs))
            finally:
                await conn.close()


if __name__ == "__main__":
    unittest.main()

