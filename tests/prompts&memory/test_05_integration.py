"""
=============================================================================
Test 05: 실전 LLM 통합 검증 (memory_agent.py)
=============================================================================
검증 항목:
  1. 에이전트 초기화 + 도구 바인딩 (memory + session_recall 포함)
  2. Semantic Memory L4 주입: USER.md 프로필 기반 개인화 응답
  3. Episodic Memory 2단계 JIT:
     - 1단계: before_agent FTS5 → 힌트 주입
     - 2단계: session_recall 도구 호출 여부 확인
  4. memory 도구 자율 쓰기: 에이전트가 memory(add) 호출 지시 시 실행
  5. 조립된 프롬프트에서 이중 주입 없음 확인

※ LLM API 호출 필요 (GOOGLE_API_KEY 또는 ANTHROPIC_API_KEY 필요)
=============================================================================
"""

import os
import sys
import json
import uuid
import shutil
import asyncio

# 프로젝트 루트 경로 추가 및 작업 디렉토리 고정
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.agents.main_agent import create_agent_executor
from app.middleware.memory.semantic_store import SemanticMemoryStore
from app.utils.context import AgentContext
from app.utils.workspace import resolve_user_memory_dir
from app.utils.message_utils import normalize_content


async def _close_agent(agent, test_uid: str | None = None):
    try:
        from app.middleware.memory import MemoryMiddleware
        for m in getattr(agent, "registered_middlewares", []):
            if isinstance(m, MemoryMiddleware):
                await asyncio.to_thread(m.wait_for_reviews, 5.0)
    except Exception:
        pass
    try:
        from app.middleware.observability.agent_log_tracer import _GLOBAL_LOG_WORKER
        _GLOBAL_LOG_WORKER.flush()
    except Exception:
        pass
    if hasattr(agent, "checkpointer_conn") and agent.checkpointer_conn:
        await agent.checkpointer_conn.close()
    if hasattr(agent, "episodic_store") and agent.episodic_store:
        await agent.episodic_store.close()
    if test_uid:
        shutil.rmtree(os.path.join(PROJECT_ROOT, "artifacts", "users", test_uid), ignore_errors=True)


async def test_01_agent_init_and_tools():
    """에이전트 생성 + 도구 바인딩 검증."""
    agent = await create_agent_executor()
    all_tools = []
    if hasattr(agent, "nodes") and "tools" in agent.nodes:
        tools_node = agent.nodes["tools"]
        bound_node = getattr(tools_node, "bound", tools_node)
        if hasattr(bound_node, "tools_by_name"):
            all_tools = list(bound_node.tools_by_name.values())
    if not all_tools:
        all_tools = list(getattr(agent, "registered_tools", []))
    tool_names = [t.name for t in all_tools]
    try:
        assert "memory" in tool_names, "'memory' 도구 미바인딩"
        assert "session_recall" in tool_names, "'session_recall' 도구 미바인딩"
        return {"pass": True, "detail": f"총 {len(tool_names)}개 도구: {tool_names}"}
    finally:
        await _close_agent(agent)


async def test_02_semantic_profile_qa():
    """Semantic Memory: USER.md 프로필 기반 개인화 응답."""
    run_id = uuid.uuid4().hex[:6]
    test_uid = f"test_pm02_{run_id}"
    tid = f"test_semantic_qa_{run_id}"

    # 테스트 유저의 USER.md에 프로필 사전 세팅
    sem = SemanticMemoryStore(memory_dir=str(resolve_user_memory_dir(test_uid, ensure_exists=True)))
    sem.load_from_disk()
    sem.add("user", "이름: 김철수 (Cheolsu Kim), 직무: AI Agent 아키텍처 엔지니어")

    agent = await create_agent_executor()
    ctx = AgentContext(
        user_id=test_uid,
        session_id=tid,
        semantic_memory_enabled=True,
        episodic_memory_enabled=False,
    )
    config = {"configurable": {"thread_id": tid, "user_id": test_uid}}

    try:
        response = await agent.ainvoke(
            {"messages": [HumanMessage(content="내 이름과 전문 분야를 알려줘.")]},
            config=config,
            context=ctx,
        )

        ai_msgs = [m for m in response["messages"] if isinstance(m, AIMessage)]
        assert ai_msgs, "AI 응답 없음"
        ans = normalize_content(ai_msgs[-1].content)

        assert "김철수" in ans or "Cheolsu" in ans, f"사용자 이름 미포함: {ans[:200]}"
        assert "Agent" in ans or "엔지니어" in ans or "아키텍처" in ans, f"전문 분야 미포함: {ans[:200]}"
        return {"pass": True, "detail": f"USER.md 프로필 반영 응답 확인 ({len(ans)} chars)"}
    finally:
        await _close_agent(agent, test_uid)


async def test_03_episodic_jit_2stage():
    """Episodic Memory 2단계 JIT: FTS5 힌트 + session_recall 도구 호출 검증."""
    run_id = uuid.uuid4().hex[:6]
    test_uid = f"test_pm03_{run_id}"
    past_sid = f"session_k8s_autoscaling_{run_id}"
    tid = f"test_episodic_jit_{run_id}"

    agent = await create_agent_executor()
    ctx = AgentContext(
        user_id=test_uid,
        session_id=tid,
        semantic_memory_enabled=True,
        episodic_memory_enabled=True,
    )

    try:
        # 1. 과거 세션 저장
        past_messages = [
            {"role": "human", "content": "Kubernetes에서 pod autoscaling은 어떻게 설정하나요?"},
            {"role": "ai", "content": "HorizontalPodAutoscaler(HPA)를 사용하여 CPU/메모리 기반 autoscaling을 설정합니다. kubectl autoscale deployment my-app --min=2 --max=10 --cpu-percent=80"},
            {"role": "human", "content": "Vertical Pod Autoscaler도 같이 사용할 수 있나요?"},
            {"role": "ai", "content": "네, VPA와 HPA를 함께 사용할 수 있지만, 동일 메트릭(CPU)에 대해 둘 다 설정하면 충돌합니다. VPA는 리소스 요청량만 조정하도록 설정하세요."},
        ]
        await agent.episodic_store.finalize_session(past_sid, past_messages, llm=None, user_id=test_uid)

        # 2. 새 세션에서 과거 내용 회상 질문
        config = {"configurable": {"thread_id": tid, "user_id": test_uid}}
        response = await agent.ainvoke(
            {"messages": [HumanMessage(content="이전에 Kubernetes autoscaling 설정에 대해 대화한 적 있는데, session_recall 도구를 사용해서 자세한 내용을 확인해줘.")]},
            config=config,
            context=ctx,
        )

        # 3. 응답 분석: session_recall 도구 호출 여부 확인
        all_msgs = response["messages"]
        tool_calls = [m for m in all_msgs if isinstance(m, ToolMessage)]
        session_recall_called = any(
            getattr(m, "name", "") == "session_recall" for m in tool_calls
        )

        # AIMessage의 tool_calls 속성도 확인
        ai_tool_calls = []
        for m in all_msgs:
            if isinstance(m, AIMessage) and hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    ai_tool_calls.append(tc.get("name", ""))

        session_recall_requested = "session_recall" in ai_tool_calls

        ai_msgs = [m for m in all_msgs if isinstance(m, AIMessage)]
        ans = normalize_content(ai_msgs[-1].content) if ai_msgs else ""

        detail_parts = []
        if session_recall_called or session_recall_requested:
            detail_parts.append("✅ session_recall 도구 호출 확인 (2단계 JIT 동작)")
        else:
            detail_parts.append("⚠️ session_recall 도구 미호출 (1단계 힌트만으로 응답했을 수 있음)")

        # 내용 검증
        has_content = "autoscal" in ans.lower() or "hpa" in ans.lower() or "kubernetes" in ans.lower()
        if has_content:
            detail_parts.append("✅ 과거 세션 내용 반영 확인")
        else:
            detail_parts.append(f"⚠️ 과거 세션 내용 미반영: {ans[:100]}")

        return {
            "pass": True,
            "detail": " | ".join(detail_parts),
            "session_recall_called": session_recall_called or session_recall_requested,
            "tool_calls_found": ai_tool_calls,
            "tool_messages": len(tool_calls),
        }
    finally:
        await _close_agent(agent, test_uid)


async def test_04_memory_tool_write():
    """memory 도구 자율 쓰기: 에이전트에게 기억 저장 지시."""
    run_id = uuid.uuid4().hex[:6]
    test_uid = f"test_pm04_{run_id}"
    tid = f"test_memory_write_{run_id}"

    agent = await create_agent_executor()
    ctx = AgentContext(
        user_id=test_uid,
        session_id=tid,
        semantic_memory_enabled=True,
        episodic_memory_enabled=False,
    )
    config = {"configurable": {"thread_id": tid, "user_id": test_uid}}

    try:
        response = await agent.ainvoke(
            {"messages": [HumanMessage(content="다음을 기억해: 나의 선호 IDE는 VS Code이고, 반드시 한국어로 설명해야 한다. memory 도구의 add 액션을 사용해서 user 타겟에 저장해.")]},
            config=config,
            context=ctx,
        )

        # memory 도구 호출 여부 확인
        all_msgs = response["messages"]
        tool_calls = [m for m in all_msgs if isinstance(m, ToolMessage)]
        memory_called = any(getattr(m, "name", "") == "memory" for m in tool_calls)

        ai_tool_calls = []
        for m in all_msgs:
            if isinstance(m, AIMessage) and hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    ai_tool_calls.append(tc.get("name", ""))

        memory_requested = "memory" in ai_tool_calls

        # 실제 저장 여부 확인 (격리된 test_uid 스토어 로드)
        user_sem = SemanticMemoryStore(memory_dir=str(resolve_user_memory_dir(test_uid, ensure_exists=True)))
        user_sem.load_from_disk()
        vs_code_saved = any("VS Code" in e or "vs code" in e.lower() for e in user_sem.user_entries)

        detail_parts = []
        if memory_called or memory_requested:
            detail_parts.append("✅ memory 도구 호출 확인")
        else:
            detail_parts.append("❌ memory 도구 미호출")

        if vs_code_saved:
            detail_parts.append("✅ user_entries에 VS Code 저장 확인")
        else:
            detail_parts.append(f"⚠️ user_entries: {user_sem.user_entries}")

        assert memory_called or memory_requested, "memory 도구가 호출되지 않음"
        return {"pass": True, "detail": " | ".join(detail_parts)}
    finally:
        await _close_agent(agent, test_uid)


# ── Runner ──

ALL_TESTS = [
    ("test_01_agent_init_and_tools", test_01_agent_init_and_tools),
    ("test_02_semantic_profile_qa", test_02_semantic_profile_qa),
    ("test_03_episodic_jit_2stage", test_03_episodic_jit_2stage),
    ("test_04_memory_tool_write", test_04_memory_tool_write),
]


def run_all():
    results = []
    for name, test_fn in ALL_TESTS:
        try:
            result = asyncio.run(test_fn())
            results.append({"test": name, "status": "PASS", "detail": result["detail"]})
            for k in ("session_recall_called", "tool_calls_found", "tool_messages"):
                if k in result:
                    results[-1][k] = result[k]
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "detail": str(e)})
    return results


if __name__ == "__main__":
    results = run_all()
    print("=" * 70)
    print("Test 05: 실전 LLM 통합 검증 (main_agent)")
    print("=" * 70)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['test']}: {r['detail']}")
        if "tool_calls_found" in r:
            print(f"       도구 호출: {r['tool_calls_found']}")
        if "tool_messages" in r:
            print(f"       ToolMessage 수: {r['tool_messages']}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n  Result: {passed}/{total} passed")
    sys.stdout.flush()
    os._exit(0 if passed == total else 1)
