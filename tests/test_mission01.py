"""
tests/test_mission01.py

🎯 Mission 01 자동화 검증 스크립트
1. app/tools/custom_tools.py의 커스텀 도구(roll_dice, convert_currency) 구현 여부 검증
2. 각 도구의 단위 실행 및 반환값 규격 확인
3. app/agents/chatbot.py의 도구 바인딩 및 create_agent 빌드 검증

실행 방법:
  python tests/test_mission01.py
"""

import os
import sys
import asyncio

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)


async def run_mission01_test():
    print("=" * 70)
    print("🧪 [Mission 01] 커스텀 도구 및 챗봇 바인딩 검증 테스트 시작")
    print("=" * 70)

    # 1. custom_tools 모듈 및 도구 임포트 검증
    try:
        from app.tools import custom_tools
    except ImportError as e:
        print(f"❌ [FAIL] app.tools.custom_tools 임포트 실패: {e}")
        return False

    has_dice = hasattr(custom_tools, "roll_dice")
    has_curr = hasattr(custom_tools, "convert_currency")

    assert has_dice, "❌ app/tools/custom_tools.py에 'roll_dice' 도구가 구현되지 않았습니다."
    assert has_curr, "❌ app/tools/custom_tools.py에 'convert_currency' 도구가 구현되지 않았습니다."
    print("  ✅ Test 1 통과: custom_tools.py 도구 정의 확인 (roll_dice, convert_currency)")

    # 2. 도구 단위 실행 테스트
    dice_res = custom_tools.roll_dice.invoke({"num_dice": 2, "sides": 6})
    assert isinstance(dice_res, str) and ("주사위" in dice_res or "Dice" in dice_res or "합계" in dice_res or "Total" in dice_res or "[" in dice_res), (
        f"❌ roll_dice 실행 결과가 예상과 다릅니다: {dice_res}"
    )

    curr_res = custom_tools.convert_currency.invoke({"amount": 100, "from_currency": "USD", "to_currency": "KRW"})
    assert isinstance(curr_res, str) and ("환율" in curr_res or "KRW" in curr_res or "원" in curr_res), (
        f"❌ convert_currency 실행 결과가 예상과 다릅니다: {curr_res}"
    )
    print("  ✅ Test 2 통과: 각 도구의 단위 실행 및 결과 반환 확인")

    # 3. chatbot 에이전트 바인딩 검증
    from app.agents import chatbot

    try:
        agent = await chatbot.create_agent_executor()
    except Exception as e:
        print(f"❌ [FAIL] chatbot.create_agent_executor 실행 중 에러 발생: {e}")
        return False

    # 에이전트에 등록된 도구 목록 확인
    tools = getattr(agent, "tools", []) or getattr(agent, "registered_tools", [])
    if not tools and hasattr(agent, "nodes"):
        # LangGraph 노드 내부에서 도구 목록 탐색
        tools_node = agent.nodes.get("tools")
        if tools_node and hasattr(tools_node, "tools_by_name"):
            tools = list(tools_node.tools_by_name.values())

    tool_names = {getattr(t, "name", "") for t in tools}
    assert "roll_dice" in tool_names, (
        "❌ chatbot 에이전트에 'roll_dice' 도구가 바인딩되지 않았습니다.\n"
        "   app/agents/chatbot.py의 active_tools 목록에 roll_dice를 추가하세요."
    )
    assert "convert_currency" in tool_names, (
        "❌ chatbot 에이전트에 'convert_currency' 도구가 바인딩되지 않았습니다.\n"
        "   app/agents/chatbot.py의 active_tools 목록에 convert_currency를 추가하세요."
    )
    print(f"  ✅ Test 3 통과: chatbot 에이전트에 커스텀 도구 바인딩 확인 (총 {len(tools)}종)")

    # 리소스 정리
    checkpointer = getattr(agent, "checkpointer", None)
    conn = getattr(checkpointer, "conn", None)
    if conn:
        await conn.close()

    print("\n" + "=" * 70)
    print("🎉 [Mission 01] 커스텀 도구 구현 및 챗봇 결합 검증 100% 통과!")
    print("   이제 Chainlit UI에서 주사위 굴리기 및 환율 계산을 테스트하세요.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_mission01_test())
    sys.stdout.flush()
    os._exit(0 if success else 1)
