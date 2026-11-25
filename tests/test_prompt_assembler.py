"""
tests/test_prompt_assembler.py

단순화된 PromptAssembler / SkillPromptBuilder / PromptAssemblerMiddleware 오프라인 검증:
1. Static SystemMessage 순수성(세션·날짜·메모리·도구·동적 스킬 목록 미포함) + cache_control
2. sort_tools_for_cache 내장 → MCP 2단 알파벳 정렬
3. User Context HumanMessage 구조 & 마커 격리(harness_origin="user_context", transcript_skip)
4. 멀티턴/도구 루프(session_search 등) 프리픽스 바이트 불변성 + legacy recalled_memory 폴백
5. 양방향 Skill Delta (추가 + 제거 + 재추가 + 빈 초기 목록)
6. 자정 경과 시 앞단 날짜 유지 + 끝단 date_change append
7. create_agent + Compaction + PromptAssemblerMiddleware E2E (압축 후 skill_delta 자동 복원)
8. TranscriptStore / message_markers 턴 경계 격리
9. SkillPromptBuilder 파일 추가·수정·삭제 즉시 감지
10. MemoryMiddleware 3종 도구(memory, session_search, session_recall) 및 Semantic-only before_agent 검증
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from app.context import AgentContext
from app.middleware.compaction import create_compaction_middleware
from app.middleware.memory import EpisodicStore, MemoryMiddleware, SemanticMemoryStore
from app.middleware.memory.transcript_store import classify_message
from app.middleware.prompt import (
    PromptAssembler,
    SkillPromptBuilder,
    build_live_request,
    create_prompt_assembler_middleware,
    sort_tools_for_cache,
)
from app.middleware.prompt.prompt_assembler import (
    SKILL_ADDED_KEY,
    SKILL_REMOVED_KEY,
    make_date_change_message,
    make_skill_delta_message,
    make_user_context_message,
)
from app.utils.message_markers import (
    ORIGIN_DATE_CHANGE,
    ORIGIN_SKILL_DELTA,
    ORIGIN_USER_CONTEXT,
    TRANSCRIPT_SKIP_KEY,
    is_attachment,
    is_compaction_summary,
    is_user_turn_start,
    last_user_turn_start,
    message_origin,
)


class _RecordingFakeModel(GenericFakeChatModel):
    """매 모델 호출 시 전달된 메시지 목록을 기록하는 가짜 LLM."""

    recorded_calls: list = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.recorded_calls.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _msg_text(msg) -> str:
    content = getattr(msg, "content", "")
    return content if isinstance(content, str) else str(content)


def _run_turn(mw, state, tools=None, context=None):
    runtime = SimpleNamespace(context=context, config=None, execution_info=None)
    update = mw.before_model(state, runtime=runtime) or {}
    added = update.pop("messages", [])
    state.update(update)
    state["messages"] = list(state.get("messages") or []) + added
    return build_live_request(mw, state, tools=tools, context=context)


class SimplifiedPromptAssemblerTests(unittest.TestCase):
    def test_01_static_system_message_purity_and_cache_control(self):
        """② Static SystemMessage에는 순수 역할 정체성만 들어가고, 스킬 실행 지침·목록·세션·메모리는 User Context에 분리된다."""
        guidelines = "Always read SKILL.md before running a skill."
        skills = [{"name": "alpha-skill", "description": "Alpha desc", "path": "skills/alpha/SKILL.md"}]
        assembler = PromptAssembler(
            system_prompt="You are a clean static agent.",
            skill_guidelines=lambda: guidelines,
            skill_provider=lambda: skills,
            project_rules="Do not push directly to main.",
        )
        mw = create_prompt_assembler_middleware(assembler, enable_cache_control=True)
        ctx = AgentContext(
            user_id="user_a",
            session_id="sess_123",
            memory_snapshot="USER likes pytest",
        )
        state = {"messages": [HumanMessage(content="안녕", id="u1")]}
        req = _run_turn(mw, state, context=ctx)

        sys_msg = req.messages[0]
        self.assertIsInstance(sys_msg, SystemMessage)
        self.assertEqual(sys_msg.additional_kwargs, {"cache_control": {"type": "ephemeral"}})
        self.assertEqual(sys_msg.content, "You are a clean static agent.")
        for forbidden in (
            "Always read SKILL.md",
            "sess_123",
            "user_a",
            "USER likes pytest",
            "alpha-skill",
            "Do not push directly",
        ):
            self.assertNotIn(forbidden, sys_msg.content)

        # skill_guidelines는 User Context의 # skillCatalog에 포함된다
        uc_msg = req.messages[1]
        self.assertIn("# skillCatalog", uc_msg.content)
        self.assertIn("Always read SKILL.md before running a skill.", uc_msg.content)
        self.assertLess(
            uc_msg.content.index("Always read SKILL.md before running a skill."),
            uc_msg.content.index("alpha-skill"),
        )

        # enable_cache_control=False 및 clear_static_cache 확인
        mw_nocache = create_prompt_assembler_middleware(assembler, enable_cache_control=False)
        req_nc = build_live_request(mw_nocache, {"messages": [HumanMessage(content="hi", id="u2")]}, context=ctx)
        self.assertEqual(req_nc.messages[0].additional_kwargs, {})

        guidelines = "Updated policy text."
        self.assertIn("Always read SKILL.md", assembler.resolve_skill_guidelines())
        assembler.clear_static_cache()
        self.assertIn("Updated policy text.", assembler.resolve_skill_guidelines())

    def test_02_tool_sorting_builtin_then_mcp(self):
        """① tools 정렬: 내장 도구 이름순 → MCP(mcp__*) 도구 이름순."""
        @tool
        def web_search(q: str) -> str:
            """search."""
            return q

        @tool
        def file_read(p: str) -> str:
            """read."""
            return p

        @tool
        def bash_command(c: str) -> str:
            """bash."""
            return c

        raw_tools = [
            {"name": "mcp__zebra__run"},
            web_search,
            {"name": "mcp__alpha__query"},
            file_read,
            bash_command,
        ]
        sorted_names = [
            t.get("name") if isinstance(t, dict) else t.name
            for t in sort_tools_for_cache(raw_tools)
        ]
        self.assertEqual(
            sorted_names,
            ["bash_command", "file_read", "web_search", "mcp__alpha__query", "mcp__zebra__run"],
        )

        assembler = PromptAssembler(system_prompt="Rules")
        mw = create_prompt_assembler_middleware(assembler)
        req = _run_turn(mw, {"messages": [HumanMessage(content="hi", id="u1")]}, tools=raw_tools)
        req_names = [t.get("name") if isinstance(t, dict) else t.name for t in req.tools]
        self.assertEqual(req_names, sorted_names)

    def test_03_user_context_structure_and_marker_isolation(self):
        """③ User Context는 SystemMessage 바로 뒤에 위치하며 # sessionContext·# skillCatalog(지침+목록)·# memorySnapshot·# projectRules를 포함한다."""
        skills = [{"name": "beta-skill", "description": "Beta helper", "path": "skills/beta/SKILL.md"}]
        assembler = PromptAssembler(
            system_prompt="Static rules",
            skill_guidelines="Read SKILL.md first.",
            skill_provider=lambda: skills,
            project_rules="Use pytest -q.",
        )
        mw = create_prompt_assembler_middleware(assembler)
        ctx = AgentContext(
            user_id="alice",
            session_id="sess_uc_1",
            memory_snapshot="MEMORY: prefers Korean summaries",
        )
        state = {"messages": [HumanMessage(content="작업 시작하자", id="u1")]}
        req = _run_turn(mw, state, context=ctx)

        self.assertEqual(len(req.messages), 3)
        uc = req.messages[1]
        self.assertIsInstance(uc, HumanMessage)
        self.assertEqual(message_origin(uc), ORIGIN_USER_CONTEXT)
        self.assertTrue(uc.additional_kwargs.get(TRANSCRIPT_SKIP_KEY))
        self.assertFalse(is_user_turn_start(uc))

        pos_sc = uc.content.index("# sessionContext")
        pos_sk = uc.content.index("# skillCatalog")
        pos_guide = uc.content.index("Read SKILL.md first.")
        pos_beta = uc.content.index("beta-skill")
        pos_mem = uc.content.index("# memorySnapshot")
        pos_pr = uc.content.index("# projectRules")
        self.assertTrue(pos_sc < pos_sk < pos_guide < pos_beta < pos_mem < pos_pr)
        self.assertIn("Session ID: sess_uc_1", uc.content)
        self.assertIn("User ID: alice", uc.content)
        self.assertIn("Session Workspace Root:", uc.content)
        self.assertIn("beta-skill", uc.content)
        self.assertIn("MEMORY: prefers Korean summaries", uc.content)
        self.assertIn("Use pytest -q.", uc.content)

    def test_04_multiturn_tool_loop_prefix_invariance(self):
        """④ 멀티턴 + 도구 루프(session_search 등)에서 프리픽스 바이트가 100% 보존되고 legacy recalled_memory도 User Context에 반영된다."""
        assembler = PromptAssembler(system_prompt="Static")
        mw = create_prompt_assembler_middleware(assembler)

        ctx = AgentContext(
            user_id="u1",
            session_id="s_multi",
            memory_snapshot="MEMORY (agent's personal notes)\n- Uses FastAPI",
        )
        state = {"messages": [HumanMessage(content="1턴 질문", id="h1")]}

        # 턴 1-1: 초기 조립
        req1 = _run_turn(mw, state, context=ctx)
        self.assertEqual(len(req1.messages), 3)
        self.assertIn("- Uses FastAPI", req1.messages[1].content)

        # 같은 턴 도구 루프 재호출 (session_search 도구 결과 포함): 앞부분 100% 일치
        state["messages"] += [
            AIMessage(
                content="",
                id="a1",
                tool_calls=[{"name": "session_search", "args": {"query": "FastAPI"}, "id": "tc1"}],
            ),
            ToolMessage(content='{"results": [{"session_id": "s_prev"}]}', tool_call_id="tc1", name="session_search", id="t1"),
        ]
        req1_loop = _run_turn(mw, state, context=ctx)
        self.assertEqual(len(req1_loop.messages), 5)
        for idx in range(len(req1.messages)):
            self.assertEqual(_msg_text(req1.messages[idx]), _msg_text(req1_loop.messages[idx]))

        # 턴 2: 새 사용자 질문에도 앞부분 [00]~[04] 바이트 100% 일치
        state["messages"] += [
            AIMessage(content="이전 세션을 확인했습니다.", id="a2"),
            HumanMessage(content="2턴 질문", id="h2"),
        ]
        t2_out = _run_turn(mw, state, context=ctx)
        self.assertEqual(len(t2_out.messages), 7)
        for idx in range(len(req1_loop.messages)):
            self.assertEqual(_msg_text(req1_loop.messages[idx]), _msg_text(t2_out.messages[idx]))

        # legacy recalled_memory-only fallback 검증
        legacy_ctx = AgentContext(user_id="u1", session_id="s_legacy", recalled_memory="LEGACY SNAPSHOT ENTRY")
        legacy_out = _run_turn(
            create_prompt_assembler_middleware(PromptAssembler(system_prompt="Static")),
            {"messages": [HumanMessage(content="hi", id="hl")]},
            context=legacy_ctx,
        )
        self.assertIn("LEGACY SNAPSHOT ENTRY", legacy_out.messages[1].content)

    def test_05_bidirectional_skill_delta_and_empty_initial(self):
        """⑤ 양방향 Skill Delta (추가·제거·재추가·무변화·빈 초기 목록) 및 프리픽스 불변 검증."""
        skills = [
            {"name": "skill-a", "description": "Skill A", "path": "skills/a/SKILL.md"},
            {"name": "skill-b", "description": "Skill B", "path": "skills/b/SKILL.md"},
        ]
        assembler = PromptAssembler(system_prompt="Static", skill_provider=lambda: list(skills))
        mw = create_prompt_assembler_middleware(assembler)
        ctx = AgentContext(user_id="u1", session_id="s_delta")

        # Turn 1: 초기 [a, b] -> skillCatalog에만, delta 없음
        state = {"messages": [HumanMessage(content="T1", id="u1")]}
        out1 = _run_turn(mw, state, context=ctx)
        self.assertEqual([s["name"] for s in state["initial_skills"]], ["skill-a", "skill-b"])
        self.assertFalse(any(message_origin(m) == ORIGIN_SKILL_DELTA for m in out1.messages))
        self.assertIn("skill-a", out1.messages[1].content)
        self.assertIn("skill-b", out1.messages[1].content)

        # Turn 2: +skill-c
        skills.append({"name": "skill-c", "description": "Skill C", "path": "skills/c/SKILL.md"})
        state["messages"] += [AIMessage(content="R1", id="a1"), HumanMessage(content="T2", id="u2")]
        out2 = _run_turn(mw, state, context=ctx)
        d2 = out2.messages[-1]
        self.assertEqual(message_origin(d2), ORIGIN_SKILL_DELTA)
        self.assertEqual(d2.additional_kwargs[SKILL_ADDED_KEY], ["skill-c"])
        self.assertEqual(d2.additional_kwargs[SKILL_REMOVED_KEY], [])
        self.assertEqual(_msg_text(out2.messages[0]), _msg_text(out1.messages[0]))
        self.assertEqual(_msg_text(out2.messages[1]), _msg_text(out1.messages[1]))

        # Turn 3: -skill-b
        skills[:] = [s for s in skills if s["name"] != "skill-b"]
        state["messages"] += [AIMessage(content="R2", id="a2"), HumanMessage(content="T3", id="u3")]
        out3 = _run_turn(mw, state, context=ctx)
        d3 = out3.messages[-1]
        self.assertEqual(message_origin(d3), ORIGIN_SKILL_DELTA)
        self.assertEqual(d3.additional_kwargs[SKILL_ADDED_KEY], [])
        self.assertEqual(d3.additional_kwargs[SKILL_REMOVED_KEY], ["skill-b"])
        self.assertIn("skill-b", d3.content)

        # Turn 4: +skill-b & -skill-a 동시
        skills[:] = [
            {"name": "skill-b", "description": "Skill B", "path": "skills/b/SKILL.md"},
            {"name": "skill-c", "description": "Skill C", "path": "skills/c/SKILL.md"},
        ]
        state["messages"] += [AIMessage(content="R3", id="a3"), HumanMessage(content="T4", id="u4")]
        out4 = _run_turn(mw, state, context=ctx)
        d4 = out4.messages[-1]
        self.assertEqual(d4.additional_kwargs[SKILL_ADDED_KEY], ["skill-b"])
        self.assertEqual(d4.additional_kwargs[SKILL_REMOVED_KEY], ["skill-a"])

        # Turn 5: 변화 없음 -> delta 추가 안 됨
        state["messages"] += [AIMessage(content="R4", id="a4"), HumanMessage(content="T5", id="u5")]
        out5 = _run_turn(mw, state, context=ctx)
        self.assertNotEqual(message_origin(out5.messages[-1]), ORIGIN_SKILL_DELTA)

        # 빈 초기 목록 [] -> 이후 +skill-x
        empty_skills: list = []
        mw_empty = create_prompt_assembler_middleware(
            PromptAssembler(system_prompt="Static", skill_provider=lambda: list(empty_skills))
        )
        s_empty = {"messages": [HumanMessage(content="start", id="e1")]}
        e1 = _run_turn(mw_empty, s_empty, context=AgentContext(session_id="s_empty"))
        self.assertEqual(s_empty["initial_skills"], [])
        self.assertNotIn("# skillCatalog", e1.messages[1].content)

        empty_skills.append({"name": "skill-x", "description": "New X", "path": "skills/x/SKILL.md"})
        s_empty["messages"] += [AIMessage(content="ok", id="ea1"), HumanMessage(content="next", id="e2")]
        e2 = _run_turn(mw_empty, s_empty, context=AgentContext(session_id="s_empty"))
        self.assertEqual(message_origin(e2.messages[-1]), ORIGIN_SKILL_DELTA)
        self.assertEqual(e2.messages[-1].additional_kwargs[SKILL_ADDED_KEY], ["skill-x"])

        # guidelines만 있고 초기 스킬이 비어도 # skillCatalog는 생성된다
        mw_guide_only = create_prompt_assembler_middleware(
            PromptAssembler(
                system_prompt="Static",
                skill_guidelines="Use file_read on SKILL.md.",
                skill_provider=lambda: [],
            )
        )
        req_g = _run_turn(
            mw_guide_only,
            {"messages": [HumanMessage(content="hi", id="g1")]},
            context=AgentContext(session_id="s_guide_only"),
        )
        self.assertIn("# skillCatalog", req_g.messages[1].content)
        self.assertIn("Use file_read on SKILL.md.", req_g.messages[1].content)
        self.assertNotIn("<skills>", req_g.messages[1].content)

    def test_06_midnight_date_change_preserves_prefix(self):
        """⑥ 자정이 지나 날짜가 바뀌어도 User Context의 시작 날짜는 고정되고 대화 끝에만 date_change가 붙는다."""
        assembler = PromptAssembler(system_prompt="Static")
        mw = create_prompt_assembler_middleware(assembler)
        ctx = AgentContext(user_id="u1", session_id="s_midnight")

        with patch("app.middleware.prompt.prompt_assembler.get_local_iso_date", return_value="2026-10-23"):
            state = {"messages": [HumanMessage(content="밤 11시 59분", id="m1")]}
            out1 = _run_turn(mw, state, context=ctx)
            self.assertIn("Current Date: 2026-10-23", out1.messages[1].content)

        with patch("app.middleware.prompt.prompt_assembler.get_local_iso_date", return_value="2026-10-24"):
            state["messages"] += [AIMessage(content="네", id="ma1"), HumanMessage(content="자정 넘김", id="m2")]
            out2 = _run_turn(mw, state, context=ctx)

        self.assertIn("Current Date: 2026-10-23", out2.messages[1].content)
        self.assertEqual(_msg_text(out2.messages[1]), _msg_text(out1.messages[1]))
        self.assertEqual(message_origin(out2.messages[-1]), ORIGIN_DATE_CHANGE)
        self.assertIn("2026-10-24", out2.messages[-1].content)

    def test_07_create_agent_compaction_reemits_skill_delta(self):
        """⑦ create_agent + Compaction + PromptAssemblerMiddleware E2E: 압축으로 이전 delta가 사라지면 재발행."""
        skills = [
            {"name": "skill-a", "description": "Skill A", "path": "skills/a/SKILL.md"},
            {"name": "skill-b", "description": "Skill B", "path": "skills/b/SKILL.md"},
        ]
        main_llm = _RecordingFakeModel(
            messages=iter([
                AIMessage(content="Turn 1 reply " + "x" * 200),
                AIMessage(content="Turn 2 reply " + "y" * 200),
                AIMessage(content="Turn 3 reply after compaction"),
            ])
        )
        main_llm.recorded_calls = []
        summ_llm = _RecordingFakeModel(
            messages=iter([AIMessage(content="SUMMARY: conversation up to turn 2") for _ in range(3)])
        )
        summ_llm.recorded_calls = []

        assembler = PromptAssembler(
            system_prompt="You are an E2E test agent.",
            skill_provider=lambda: list(skills),
        )
        prompt_mw = create_prompt_assembler_middleware(assembler)
        compaction_mws = create_compaction_middleware(
            main_llm,
            trigger_tokens=300,
            keep_tokens=80,
            summary_llm=summ_llm,
        )

        agent = create_agent(
            model=main_llm,
            tools=[],
            middleware=[*compaction_mws, prompt_mw],
            checkpointer=InMemorySaver(),
            context_schema=AgentContext,
        )
        cfg = {"configurable": {"thread_id": "e2e-compaction-skill-delta"}}
        ctx = AgentContext(user_id="e2e_user", session_id="e2e-compaction-skill-delta")

        # Turn 1: initial [a, b]
        agent.invoke({"messages": [HumanMessage(content="Start session " + "p" * 400)]}, cfg, context=ctx)
        # Turn 2: +skill-c
        skills.append({"name": "skill-c", "description": "Skill C", "path": "skills/c/SKILL.md"})
        agent.invoke({"messages": [HumanMessage(content="Added skill c " + "q" * 600)]}, cfg, context=ctx)
        # Turn 3: trigger compaction -> old skill_delta is compacted away, PromptAssemblerMiddleware re-emits it!
        agent.invoke({"messages": [HumanMessage(content="Final turn " + "r" * 800)]}, cfg, context=ctx)

        turn3_call_msgs = main_llm.recorded_calls[-1]
        self.assertTrue(any(is_compaction_summary(m) for m in turn3_call_msgs))
        reemitted_deltas = [m for m in turn3_call_msgs if message_origin(m) == ORIGIN_SKILL_DELTA]
        self.assertEqual(len(reemitted_deltas), 1)
        self.assertEqual(reemitted_deltas[0].additional_kwargs[SKILL_ADDED_KEY], ["skill-c"])

        # UserContext는 state["messages"]에 영속 저장되지 않아야 함
        saved_msgs = agent.get_state(cfg).values["messages"]
        self.assertFalse(any(message_origin(m) == ORIGIN_USER_CONTEXT for m in saved_msgs))

    def test_08_transcript_and_turn_boundary_isolation(self):
        """⑧ PromptAssembler 메시지는 원문(Transcript)과 사용자 턴 경계 판별에서 제외된다."""
        uc = make_user_context_message({"sessionContext": "- Session ID: s1"})
        sd = make_skill_delta_message(
            [{"name": "s1", "description": "d", "path": "skills/s1/SKILL.md"}],
            [],
        )
        dc = make_date_change_message("2026-10-25")
        real_u1 = HumanMessage(content="진짜 질문 1")
        real_u2 = HumanMessage(content="진짜 질문 2")

        for m in (uc, sd, dc):
            self.assertIsNone(classify_message(m))
            self.assertFalse(is_user_turn_start(m))

        for m in (sd, dc):
            self.assertTrue(is_attachment(m))
        self.assertFalse(is_attachment(uc))

        convo = [uc, real_u1, AIMessage(content="a1"), real_u2, sd, dc]
        self.assertEqual(last_user_turn_start(convo), 3)

    def test_09_skill_builder_detects_fs_changes(self):
        """⑨ SkillPromptBuilder는 실제 디스크의 스킬 추가·수정·삭제를 즉시 감지한다."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            alpha_dir = root / "alpha"
            alpha_dir.mkdir()
            (alpha_dir / "SKILL.md").write_text(
                "---\nname: alpha\ndescription: First alpha\n---\n# Alpha\n",
                encoding="utf-8",
            )
            builder = SkillPromptBuilder(skills_dirs=[str(root)], guidelines_path=None)
            self.assertEqual([s["name"] for s in builder.list_skills()], ["alpha"])

            # 스킬 추가
            beta_dir = root / "beta"
            beta_dir.mkdir()
            (beta_dir / "SKILL.md").write_text(
                "---\nname: beta\ndescription: Second beta\n---\n# Beta\n",
                encoding="utf-8",
            )
            self.assertEqual([s["name"] for s in builder.list_skills()], ["alpha", "beta"])

            # 스킬 설명 수정
            (alpha_dir / "SKILL.md").write_text(
                "---\nname: alpha\ndescription: Updated alpha description\n---\n# Alpha\n",
                encoding="utf-8",
            )
            listed = {s["name"]: s["description"] for s in builder.list_skills()}
            self.assertEqual(listed["alpha"], "Updated alpha description")

            # 스킬 삭제
            (beta_dir / "SKILL.md").unlink()
            beta_dir.rmdir()
            self.assertEqual([s["name"] for s in builder.list_skills()], ["alpha"])

    def test_10_memory_middleware_episodic_tools_and_semantic_only_prefetch(self):
        """⑩ MemoryMiddleware는 [memory, session_search, session_recall] 3종 도구를 등록하고 Semantic만 User Context에 프리페치한다."""
        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                mem_dir = Path(tmpdir) / "mem"
                mem_dir.mkdir(parents=True)
                (mem_dir / "MEMORY.md").write_text("- Always write pytest tests\n", encoding="utf-8")
                (mem_dir / "USER.md").write_text("- Preferred language: Korean\n", encoding="utf-8")
                epi_path = str(Path(tmpdir) / "episodic.db")

                sem = SemanticMemoryStore(memory_dir=str(mem_dir))
                sem.load_from_disk()
                epi = EpisodicStore(db_path=epi_path)
                await epi.setup()
                await epi.finalize_session(
                    "sess_zephyr_1",
                    [
                        {"role": "human", "content": "프로젝트 코드네임을 Zephyr-9443으로 정했어."},
                        {"role": "ai", "content": "네, Zephyr-9443으로 기록하겠습니다."},
                    ],
                    llm=None,
                )

                mw = MemoryMiddleware(semantic_store=sem, episodic_store=epi)
                try:
                    self.assertEqual(
                        [t.name for t in mw.tools],
                        ["memory", "session_search", "session_recall"],
                    )

                    ctx = AgentContext(user_id="default", session_id="sess_now")
                    rt = SimpleNamespace(context=ctx, config={"configurable": {"thread_id": "sess_now"}})
                    await mw.abefore_agent({"messages": [HumanMessage(content="Zephyr 기억나?")]}, rt)
                    self.assertIn("Always write pytest tests", ctx.memory_snapshot)
                    self.assertIn("Preferred language: Korean", ctx.memory_snapshot)
                    self.assertNotIn("EPISODIC MEMORY", ctx.memory_snapshot)
                    self.assertEqual(ctx.recalled_memory, ctx.memory_snapshot)

                    # episodic_memory_enabled=False 시 search/recall 둘 다 비활성화
                    disabled_rt = SimpleNamespace(context=AgentContext(episodic_memory_enabled=False))
                    self.assertEqual(mw._disabled_tool_names(disabled_rt), {"session_search", "session_recall"})

                    # Pull 1단계(session_search) & 2단계(session_recall) 실행 검증
                    search_tool = next(t for t in mw.tools if t.name == "session_search")
                    recall_tool = next(t for t in mw.tools if t.name == "session_recall")
                    search_res = json.loads(await search_tool.ainvoke({"query": "Zephyr", "limit": 3}))
                    self.assertEqual(search_res["count"], 1)
                    self.assertEqual(search_res["results"][0]["session_id"], "sess_zephyr_1")

                    recall_res = json.loads(
                        await recall_tool.ainvoke({"session_id": "sess_zephyr_1", "anchor_message": "Zephyr"})
                    )
                    self.assertGreaterEqual(recall_res["message_count"], 2)
                    self.assertTrue(any("Zephyr-9443" in m["content"] for m in recall_res["messages"]))
                finally:
                    mw._review_queue.shutdown()
                    mw._review_executor.shutdown(wait=True, cancel_futures=True)
                    await epi.close()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
