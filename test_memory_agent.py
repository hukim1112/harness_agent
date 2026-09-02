"""
Comprehensive Test Script for memory_agent.py
Tests:
1. Agent Initialization & Tool Binding Verification
2. Semantic Memory (USER.md / MEMORY.md) L4 Injection & Question Answering
3. Episodic Memory (Session 1 Finalize -> Session 2 FTS5 Prefetch & Recall)
"""

import os
import sys
import json
import asyncio
from dotenv import load_dotenv

# Load .env
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.agents.memory_agent import create_agent_executor
from app.utils.context import AgentContext


async def run_memory_agent_test():
    print("=" * 70)
    print("🧠 Memory Agent 종합 검증 테스트 시작")
    print("=" * 70)

    # -------------------------------------------------------------
    # Test 1: Agent Initialization & Structure Verification
    # -------------------------------------------------------------
    print("\n[Test 1] 에이전트 생성 및 구조 검증")
    agent = await create_agent_executor()
    assert agent is not None, "에이전트 인스턴스가 생성되어야 합니다."

    # 도구 확인
    tool_names = [t.name for t in getattr(agent, "registered_tools", [])]
    print(f"  - 바인딩된 총 도구 수: {len(tool_names)}")
    print(f"  - 도구 목록: {tool_names}")
    assert "memory" in tool_names, "'memory' 도구가 바인딩되어야 합니다."
    assert "session_recall" in tool_names, "'session_recall' 도구가 바인딩되어야 합니다."
    print("  ✅ Test 1 통과: 도구 및 에이전트 초기화 정상")

    # -------------------------------------------------------------
    # Test 2: Semantic Memory (USER.md) 반영 질의응답
    # -------------------------------------------------------------
    print("\n[Test 2] Semantic Memory (USER.md) 반영 질의응답 테스트")
    ctx = AgentContext(
        semantic_memory_enabled=True,
        episodic_memory_enabled=True,
        user_permission="ADMIN",
        active_project="agent_lab"
    )
    
    config = {
        "configurable": {
            "thread_id": "test_semantic_session_101"
        }
    }

    # 질문: USER.md에 저장된 사용자 프로필에 대해 묻기
    query_1 = "내 프로필과 전문 분야, 그리고 내가 선호하는 설명 스타일에 대해 알려줘."
    print(f"  - 사용자 질문: '{query_1}'")

    input_payload = {
        "messages": [HumanMessage(content=query_1)],
    }

    response_1 = await agent.ainvoke(
        input_payload,
        config=config,
        context=ctx
    )

    from app.utils.message_utils import normalize_content

    last_ai_msg = [m for m in response_1["messages"] if isinstance(m, AIMessage)][-1]
    ans_1 = normalize_content(last_ai_msg.content)
    print(f"\n  🤖 에이전트 답변 요약:\n{ans_1[:350]}...\n")

    # 검증: USER.md의 핵심 키워드(김철수, AI 소프트웨어 엔지니어 등)가 답변에 포함되어 있는지 확인
    assert "김철수" in ans_1 or "Cheolsu" in ans_1, "답변에 사용자 이름이 포함되어야 합니다."
    assert "엔지니어" in ans_1 or "Engineer" in ans_1 or "아키텍처" in ans_1, "답변에 직업/전문분야가 포함되어야 합니다."
    print("  ✅ Test 2 통과: USER.md 프로필 기반 정확한 개인화 응답 확인")

    # -------------------------------------------------------------
    # Test 3: Episodic Memory (세션 1 저장 -> 세션 2 FTS5 검색 & Anchor 인출)
    # -------------------------------------------------------------
    print("\n[Test 3] Episodic Memory (과거 세션 저장 -> 새 세션에서 검색 및 회상)")
    
    # 3-1: 세션 A 대화 생성 및 요약 저장 (Finalize)
    session_a_id = "session_project_arch_001"
    messages_session_a = [
        {"role": "human", "content": "agent_lab 프로젝트의 5계층 프롬프트 아키텍처에 대해 논의하고 싶어. Boundary marker는 어디에 들어가?"},
        {"role": "ai", "content": "agent_lab의 5계층 프롬프트에서 Boundary marker(__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__)는 Layer 2 (도구 스키마 및 스킬)의 끝에 배치되어 정적 프리픽스 캐시를 보호합니다."},
        {"role": "human", "content": "좋아. 그리고 우리는 JIT 방식의 session_recall 도구만 에이전트에게 주기로 결정했지?"},
        {"role": "ai", "content": "맞습니다. session_search는 미들웨어가 자동으로 검색하고, 에이전트에게는 session_recall 도구만 부여하여 도구 피로를 방지하기로 확정했습니다."},
    ]

    await agent.episodic_store.finalize_session(
        session_id=session_a_id,
        messages=messages_session_a,
        llm=None # Fast rule-based summary for test
    )
    print(f"  - 세션 A ({session_a_id}) 대화 및 요약 저장 완료")

    # 3-2: 세션 B에서 과거 대화 회상 질문
    config_b = {
        "configurable": {
            "thread_id": "test_session_b_202"
        }
    }
    query_2 = "우리가 이전에 session_recall 도구와 boundary marker 위치에 대해 어떤 결정을 내렸었는지 기억해?"
    print(f"  - 새 세션 B 질문: '{query_2}'")

    input_payload_2 = {
        "messages": [HumanMessage(content=query_2)],
    }

    response_2 = await agent.ainvoke(
        input_payload_2,
        config=config_b,
        context=ctx
    )

    last_ai_msg_2 = [m for m in response_2["messages"] if isinstance(m, AIMessage)][-1]
    ans_2 = normalize_content(last_ai_msg_2.content)
    print(f"\n  🤖 에이전트 회상 답변 요약:\n{ans_2[:400]}...\n")

    # 검증: 과거 세션의 결정 사항(Boundary marker 위치 또는 session_recall 도구 관련 내용)이 답변에 반영되었는지 확인
    assert "Layer 2" in ans_2 or "경계" in ans_2 or "boundary" in ans_2.lower() or "session_recall" in ans_2, \
        "답변에 과거 세션에서 합의한 내용이 회상되어야 합니다."
    print("  ✅ Test 3 통과: FTS5 에피소드 검색 및 과거 세션 회상 정상 동작")

    # -------------------------------------------------------------
    # 정리 (Clean up DB connections)
    # -------------------------------------------------------------
    if hasattr(agent, "checkpointer_conn"):
        await agent.checkpointer_conn.close()
    if hasattr(agent, "episodic_store"):
        await agent.episodic_store.close()

    print("\n" + "=" * 70)
    print("🎉 모든 Memory Agent 종합 검증 테스트 100% 통과!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_memory_agent_test())
