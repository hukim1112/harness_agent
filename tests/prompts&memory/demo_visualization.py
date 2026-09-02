"""
Visual Demonstration of:
1. Exact L1~L5 Prompt Assembled Payload (sent to LLM)
2. Interactive 2-Stage Episodic Memory Recall by Agent
"""

import os
import sys
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from app.agents.memory_agent import create_agent_executor
from app.utils.context import AgentContext
from app.utils.message_utils import normalize_content


async def demonstrate_prompt_and_memory():
    print("=" * 80)
    print("🎨 [1] LLM에 입력되는 실제 5-Layer 프롬프트 조립 내용 시각화")
    print("=" * 80)

    agent = await create_agent_executor()
    ctx = AgentContext(
        semantic_memory_enabled=True,
        episodic_memory_enabled=True,
        user_permission="ADMIN",
        active_project="agent_lab",
    )

    # 과거 세션 하나 심어두기
    past_session_id = "session_architecture_review_2026"
    past_messages = [
        {"role": "human", "content": "FastAPI 백엔드에서 PostgreSQL 커넥션 풀 크기는 얼마로 설정했지?"},
        {"role": "ai", "content": "PostgreSQL 커넥션 풀은 min_size=10, max_size=50, timeout=30초로 설정했습니다."},
        {"role": "human", "content": "Redis 캐시 만료 시간(TTL)은?"},
        {"role": "ai", "content": "Redis 세션 캐시 TTL은 기본 3600초(1시간)로 확정했습니다."},
    ]
    await agent.episodic_store.finalize_session(
        session_id=past_session_id,
        messages=past_messages,
        llm=None
    )

    # 1단계: before_agent가 실행되어 L4 메모리 주입 생성
    fake_state = {"messages": [HumanMessage(content="지난번에 설정한 PostgreSQL 풀 크기와 Redis TTL이 뭐였더라?")]}
    
    # MemoryMiddleware & PromptAssembler 직접 바인딩하여 before_agent 시뮬레이션
    from app.middleware.memory import MemoryMiddleware
    from app.middleware.prompt import PromptAssembler

    memory_mw = MemoryMiddleware(
        semantic_store=agent.semantic_store,
        episodic_store=agent.episodic_store,
    )
    
    # before_agent 실행하여 recalled_memory 주입
    class DummyRuntime:
        def __init__(self, ctx):
            self.context = ctx
            self.config = {"configurable": {"thread_id": "current_chat_session_999"}}

    runtime = DummyRuntime(ctx)
    memory_mw.before_agent(fake_state, runtime)

    # PromptAssembler로 실제 조립되는 시스템 프롬프트 및 메시지 생성
    session_ctx = {
        "cwd": "/mnt/c/Users/hyoun/Desktop/working_project/agent_lab",
        "session_id": "current_chat_session_999",
        "os": os.name,
        "user_permission": ctx.user_permission,
        "active_project": ctx.active_project,
        "recalled_memory": ctx.recalled_memory,
    }

    assembled_system_prompt = agent.assembler.build_system_prompt(session_ctx)

    print("\n" + "─" * 80)
    print("📜 [조립된 단일 System Message (L1 ~ L5 전 계층 실물 출력)]")
    print("─" * 80)
    print(assembled_system_prompt)
    print("─" * 80)

    # 메시지 리스트 시각화
    messages_payload = [
        SystemMessage(content=assembled_system_prompt),
        HumanMessage(content="지난번에 설정한 PostgreSQL 풀 크기와 Redis TTL이 뭐였더라? session_recall 도구로 확인해줘.")
    ]

    print("\n📨 [LLM API(Gemini 3.7 Flash)로 전송되는 최종 Messages Payload 구조]")
    for idx, msg in enumerate(messages_payload, 1):
        msg_type = msg.__class__.__name__
        content_preview = msg.content if len(msg.content) < 300 else msg.content[:300] + "\n... [중략] ..."
        print(f"\n  [{idx}] Type: {msg_type}")
        print(f"      Content Length: {len(msg.content):,} characters")
        print(f"      Preview:\n{content_preview}")

    print("\n\n" + "=" * 80)
    print("🧠 [2] 에이전트의 과거 세션 Memory 인출 실행 시연 (2-Stage JIT)")
    print("=" * 80)

    config = {"configurable": {"thread_id": "current_chat_session_999"}}
    user_query = "이전에 우리가 PostgreSQL 풀 크기랑 Redis 캐시 TTL 설정했던 것 같은데, session_recall 도구로 과거 대화를 조회해서 정확한 수치를 알려줘."

    print(f"\n👤 [사용자 질문]:\n  \"{user_query}\"")
    print("\n⚙️ 에이전트 실행 중 (before_agent FTS5 힌트 주입 ➔ LLM 판단 ➔ session_recall 호출 ➔ 최종 응답)...")

    response = await agent.ainvoke(
        {"messages": [HumanMessage(content=user_query)]},
        config=config,
        context=ctx
    )

    print("\n🔍 [에이전트 내부 실행 궤적 (Execution Trace)]:")
    all_msgs = response["messages"]
    for idx, m in enumerate(all_msgs):
        m_type = m.__class__.__name__
        if m_type == "HumanMessage":
            print(f"  [{idx+1}] 👤 HumanMessage: {m.content}")
        elif m_type == "AIMessage":
            if hasattr(m, "tool_calls") and m.tool_calls:
                print(f"  [{idx+1}] 🤖 AIMessage (도구 호출 의도 발생):")
                for tc in m.tool_calls:
                    print(f"      🎯 Tool: {tc['name']}")
                    print(f"      📦 Args: {json.dumps(tc['args'], ensure_ascii=False)}")
            else:
                ans_text = normalize_content(m.content)
                print(f"  [{idx+1}] 🤖 AIMessage (최종 답변):")
                print(f"\n{ans_text}\n")
        elif m_type == "ToolMessage":
            print(f"  [{idx+1}] 🔧 ToolMessage (도구 실행 결과 반환):")
            print(f"      Name: {getattr(m, 'name', 'unknown')}")
            tool_content = m.content if len(m.content) < 400 else m.content[:400] + "..."
            print(f"      Data: {tool_content}")

    # 리소스 정리
    if hasattr(agent, "checkpointer_conn"):
        await agent.checkpointer_conn.close()
    if hasattr(agent, "episodic_store"):
        await agent.episodic_store.close()

    print("=" * 80)
    print("✅ 시연 완료")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demonstrate_prompt_and_memory())
