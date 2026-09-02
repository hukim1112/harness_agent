"""
tests/test_main_agent.py

🎯 Mission 02 자동화 검증 스크립트
main_agent의 4대 하네스 요소(메타데이터, Self-Recovery 미들웨어, Subagent/Planning 도구, 체크포인터)가
정상적으로 구현 및 결합되었는지 검증합니다.

실행 방법:
  python tests/test_main_agent.py
"""

import os
import sys
import asyncio

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)


async def run_main_agent_test():
    print("=" * 70)
    print("🧪 [Mission 02] main_agent 하네스 및 도구 바인딩 검증 테스트 시작")
    print("=" * 70)

    # 1. 모듈 및 AGENT_METADATA 검증
    try:
        from app.agents import main_agent
    except ImportError as e:
        print(f"❌ [FAIL] app.agents.main_agent 모듈 임포트 실패: {e}")
        return False

    metadata = getattr(main_agent, "AGENT_METADATA", None)
    assert metadata is not None, "❌ AGENT_METADATA가 정의되어 있지 않습니다."
    assert metadata.get("name") == "main_agent", f"❌ AGENT_METADATA['name']이 'main_agent'가 아닙니다: {metadata.get('name')}"
    assert "description" in metadata and len(metadata["description"]) > 5, "❌ AGENT_METADATA['description']이 누락되었거나 너무 짧습니다."
    print(f"  ✅ Test 1 통과: AGENT_METADATA 검증 완료 (name: '{metadata['name']}')")

    # 2. 에이전트 팩토리 함수 실행
    factory = getattr(main_agent, "create_agent_executor", None)
    assert factory is not None, "❌ create_agent_executor 함수가 정의되어 있지 않습니다."

    try:
        agent = await factory()
    except Exception as e:
        print(f"❌ [FAIL] create_agent_executor 실행 중 에러 발생: {e}")
        return False

    assert agent is not None, "❌ create_agent_executor가 None을 반환했습니다."
    print("  ✅ Test 2 통과: create_agent_executor 에이전트 인스턴스 빌드 성공")

    # 3. 단기 기억 (AsyncSqliteSaver) 검증
    checkpointer = getattr(agent, "checkpointer", None)
    assert checkpointer is not None, "❌ 에이전트에 checkpointer가 등록되어 있지 않습니다."
    print(f"  ✅ Test 3 통과: 단기 기억 checkpointer 정상 등록 ({type(checkpointer).__name__})")

    # 4. Self-Recovery 미들웨어 노드 검증
    nodes = list(agent.nodes.keys()) if hasattr(agent, "nodes") else []
    has_call_limit = any("ModelCallLimit" in n for n in nodes)
    assert has_call_limit, (
        "❌ Self-Recovery 미들웨어(ModelCallLimitMiddleware)가 등록되지 않았습니다.\n"
        "   main_agent.py의 middleware 리스트에 ModelCallLimitMiddleware를 추가하세요."
    )
    print(f"  ✅ Test 4 통과: Self-Recovery 미들웨어 정상 탑재 확인 (활성 노드: {len(nodes)}개)")

    # 5. Sub-Agent 및 Planning 도구 바인딩 검증
    from app.tools import tools_supervisor
    expected_tool_names = {"invoke_sub_agent", "list_sub_agents", "enter_plan", "task_create"}
    supervisor_tool_names = {getattr(t, "name", "") for t in tools_supervisor}
    missing_tools = expected_tool_names - supervisor_tool_names
    assert not missing_tools, f"❌ tools_supervisor에 필수 도구가 누락되었습니다: {missing_tools}"
    print(f"  ✅ Test 5 통과: Sub-Agent 위임 및 Planning 핵심 도구 바인딩 확인 ({len(tools_supervisor)}종)")

    # 리소스 정리 (SQLite 커넥션 종료)
    conn = getattr(checkpointer, "conn", None)
    if conn:
        await conn.close()

    print("\n" + "=" * 70)
    print("🎉 [Mission 02] main_agent의 모든 하네스 구성 검증 100% 통과!")
    print("   이제 FastAPI 서버와 Chainlit UI를 띄워 대화 시나리오를 테스트하세요.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_main_agent_test())
    sys.stdout.flush()
    os._exit(0 if success else 1)
