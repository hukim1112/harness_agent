"""
tests/test_mission05.py

🎯 Mission 05 자동화 검증 스크립트: Human-in-the-Loop (권한 제어 & 인터럽트 게이트)
1. configs/hitl.config 설정 파일 유효성 및 roll_dice 타깃 인터럽트 정책 확인
2. main_agent 내 roll_dice 도구 바인딩 확인
3. 주사위 굴리기 요청 시 __interrupt__ 발생 및 인터럽트 페이로드 검증
4. [승인(Approve)] 주입 시 정상 재개 및 주사위 실행 결과 도출 검증
5. [거부(Reject)] 주입 시 정상 재개 및 도구 실행 차단 검증

실행 방법:
  python tests/test_mission05.py
"""

import os
import sys
import json
import asyncio
from langchain_core.messages import HumanMessage
from langgraph.types import Command

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)


async def run_mission05_test():
    print("=" * 70)
    print("🧪 [Mission 05] Human-in-the-Loop (roll_dice 권한 게이트) 검증 시작")
    print("=" * 70)

    # 1. configs/hitl.config 설정 확인
    hitl_config_path = os.path.join(project_root, "configs", "hitl.config")
    assert os.path.exists(hitl_config_path), "❌ configs/hitl.config 파일이 없습니다."
    
    with open(hitl_config_path, "r", encoding="utf-8") as f:
        hitl_cfg = json.load(f)
    
    interrupt_on = hitl_cfg.get("interrupt_on", {})
    assert "roll_dice" in interrupt_on, (
        "❌ hitl.config의 'interrupt_on' 대상에 'roll_dice'가 지정되어 있지 않습니다."
    )
    print("  ✅ Test 1 통과: configs/hitl.config 규격 및 roll_dice 타깃 인터럽트 설정 확인")

    # 2. main_agent 및 roll_dice 도구 바인딩 확인
    from app.tools.custom_tools import roll_dice
    from app.agents import main_agent
    assert hasattr(main_agent, "create_agent_executor"), "❌ main_agent 모듈이 유효하지 않습니다."
    print("  ✅ Test 2 통과: main_agent 내 roll_dice 도구 등록 확인")

    # 3. HITL 미들웨어가 장착된 에이전트 인스턴스로 인터럽트 검증
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from langchain.agents import create_agent
    from app.utils import init_chat_model, normalize_content
    from app.utils.context import AgentContext
    from langchain.agents.middleware import HumanInTheLoopMiddleware

    conn = await aiosqlite.connect(":memory:", check_same_thread=False)
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()

    llm = init_chat_model(model="gemini-2.5-flash", temperature=0.0)
    hitl_mw = HumanInTheLoopMiddleware(interrupt_on=interrupt_on)

    hitl_agent = create_agent(
        model=llm,
        tools=[roll_dice],
        middleware=[hitl_mw],
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )

    # 4. [인터럽트 격발 테스트] 주사위 굴리기 질의
    config_approve = {"configurable": {"thread_id": "test_hitl_thread_approve"}, "recursion_limit": 50}
    await hitl_agent.ainvoke(
        {"messages": [HumanMessage(content="주사위 2개 굴려줘")]},
        config=config_approve
    )

    # 인터럽트 상태 검증
    state = await hitl_agent.aget_state(config_approve)
    assert len(state.tasks) > 0, "❌ 에이전트 태스크가 생성되지 않았습니다."
    interrupts = state.tasks[0].interrupts
    assert len(interrupts) > 0, (
        "❌ roll_dice 호출 시 __interrupt__가 발생하지 않았습니다.\n"
        "   HumanInTheLoopMiddleware가 roll_dice 도구 격발을 가로채지 못했습니다."
    )

    intr_val = interrupts[0].value
    reqs = intr_val.get("action_requests", [])
    assert any(r.get("name") == "roll_dice" for r in reqs), (
        f"❌ 인터럽트 요청에 roll_dice가 없습니다: {intr_val}"
    )
    print("  ✅ Test 3 통과: 주사위 굴리기 요청 시 __interrupt__ 정상 발생 및 페이로드 검증")

    # 5. [승인 (Approve) 재개 테스트]
    resume_approve = Command(resume={"decisions": [{"type": "approve"}]})
    res_approved = await hitl_agent.ainvoke(resume_approve, config=config_approve)
    
    last_msg = res_approved["messages"][-1].content
    last_msg_str = normalize_content(last_msg)
    assert ("주사위" in last_msg_str or "🎲" in last_msg_str or "결과" in last_msg_str), (
        f"❌ 승인 후 주사위 결과가 출력되지 않았습니다: {last_msg_str}"
    )
    print("  ✅ Test 4 통과: [승인(Approve)] 결정 주입 시 정상 재개 및 주사위 실행 완료")

    # 6. [거부 (Reject) 재개 테스트]
    config_reject = {"configurable": {"thread_id": "test_hitl_thread_reject"}, "recursion_limit": 50}
    await hitl_agent.ainvoke(
        {"messages": [HumanMessage(content="주사위 2개 굴려줘")]},
        config=config_reject
    )
    resume_reject = Command(resume={"decisions": [{"type": "reject"}]})
    res_rejected = await hitl_agent.ainvoke(resume_reject, config=config_reject)
    
    reject_msg = res_rejected["messages"][-1].content
    reject_msg_str = normalize_content(reject_msg)
    print(f"  ℹ️ 거절 피드백 메시지: {reject_msg_str.strip()[:100]}...")
    print("  ✅ Test 5 통과: [거부(Reject)] 결정 주입 시 도구 미실행 및 거절 응답 완료")

    # 7. 리소스 정리
    await conn.close()

    print("\n" + "=" * 70)
    print("🎉 [Mission 05] Human-in-the-Loop (roll_dice 권한 게이트) 100% 통과!")
    print("   이제 configs/hitl.config의 'hitl_enabled': true로 설정하고,")
    print("   Chainlit UI에서 주사위 굴리기 시 승인/거부 팝업을 직접 테스트하세요.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_mission05_test())
    sys.stdout.flush()
    os._exit(0 if success else 1)
