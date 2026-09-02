"""
tests/test_mission07.py

🎯 Mission 07 자동화 검증 스크립트: Logging & Observability (감사 궤적 및 세션 데이터 분석)
1. configs/logging.config 설정 파일 규격 검증
2. AgentLogTracer 미들웨어 마운트 및 에이전트/도구 실행 시 비동기 JSONL 감사 궤적 적재 검증
3. log_analyzer 모듈을 통한 로그 파싱 및 핵심 메트릭(세션수, 레이턴시, 도구호출) 집계 검증
4. 터미널 관측성 대시보드 실물 시각화 출력

실행 방법:
  python tests/test_mission07.py
"""

import os
import sys
import json
import asyncio
from langchain_core.messages import HumanMessage

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)


async def run_mission07_test():
    print("=" * 70)
    print("🧪 [Mission 07] Logging & Observability (감사 궤적 & 세션 분석) 검증 시작")
    print("=" * 70)

    # 1. configs/logging.config 설정 확인
    cfg_path = os.path.join(project_root, "configs", "logging.config")
    assert os.path.exists(cfg_path), "❌ configs/logging.config 파일이 없습니다."

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    assert "logging_enabled" in cfg, "❌ logging.config에 'logging_enabled' 항목이 없습니다."
    print("  ✅ Test 1 통과: configs/logging.config 규격 확인 완료")

    # 2. AgentLogTracer 미들웨어 장착 테스트 에이전트 빌드 (노트북 7번 기반)
    from app.middleware.observability import AgentLogTracer
    from app.utils.log_analyzer import analyze_logs, print_log_dashboard
    from app.tools.custom_tools import roll_dice
    from langchain.agents import create_agent
    from app.utils import init_chat_model
    from app.utils.context import AgentContext

    test_log_dir = os.path.join(project_root, "artifacts", "logs")
    os.makedirs(test_log_dir, exist_ok=True)
    test_log_file = os.path.join(test_log_dir, "agent_audit_trail.json")

    # 이전 테스트 로그 파일이 있으면 깨끗이 초기화
    if os.path.exists(test_log_file):
        try:
            os.remove(test_log_file)
        except Exception:
            pass

    log_tracer = AgentLogTracer(log_path=test_log_file)
    llm = init_chat_model(model="gemini-3.7-flash", temperature=0.0)

    obs_agent = create_agent(
        model=llm,
        tools=[roll_dice],
        middleware=[log_tracer],
        context_schema=AgentContext,
    )

    # 3. 에이전트 실행 (도구 호출 포함)
    print("\n  [실행 1] 관측 대상 에이전트 호출 (도구 격발 포함)...")
    session_id_1 = "session_obs_demo_001"
    await obs_agent.ainvoke(
        {"messages": [HumanMessage(content="주사위 1개만 굴려줘")]},
        config={"configurable": {"thread_id": session_id_1}}
    )

    print("  [실행 2] 관측 대상 에이전트 일반 질의 호출...")
    session_id_2 = "session_obs_demo_002"
    await obs_agent.ainvoke(
        {"messages": [HumanMessage(content="안녕! 1 + 1은 뭐야?")]},
        config={"configurable": {"thread_id": session_id_2}}
    )

    # 백그라운드 워커가 디스크에 쓸 때까지 대기
    log_tracer.flush()
    await asyncio.sleep(0.5)

    # 4. 감사 궤적 파일 적재 검증
    assert os.path.exists(test_log_file), f"❌ 로그 파일이 생성되지 않았습니다: {test_log_file}"
    
    with open(test_log_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) >= 2, f"❌ 감사 궤적에 기록된 레코드가 부족합니다: {len(lines)}줄"
    print(f"  ✅ Test 2 통과: 비동기 감사 궤적 적재 확인 (총 {len(lines)}개 레코드 생성)")

    # 5. log_analyzer 모듈을 통한 메트릭 집계 및 시각화 검증
    print("\n  [분석 단계] 세션 로깅 데이터 자동 분석 엔진 구동...")
    stats = analyze_logs(test_log_dir)

    assert stats["total_sessions"] >= 2, f"❌ 고유 세션 수가 집계되지 않았습니다: {stats['total_sessions']}"
    assert stats["total_executions"] >= 2, f"❌ 총 에이전트 실행 수가 집계되지 않았습니다: {stats['total_executions']}"
    assert stats["total_tool_calls"] >= 1, f"❌ 도구 격발 수가 집계되지 않았습니다: {stats['total_tool_calls']}"
    assert "roll_dice" in stats["tool_usage"], "❌ roll_dice 도구 사용 통계가 누락되었습니다."
    print("  ✅ Test 3 통과: log_analyzer 메트릭 및 통계 집계 검증 완료")

    # 6. 실물 대시보드 시각화 출력
    print_log_dashboard(stats)

    print("=" * 70)
    print("🎉 [Mission 07] Logging & Observability (감사 궤적 & 세션 분석) 100% 통과!")
    print("   이제 configs/logging.config의 'logging_enabled': true로 설정하고,")
    print("   Chainlit 대화 후 'python -m app.utils.log_analyzer'로 관측 대시보드를 확인하세요.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_mission07_test())
    sys.stdout.flush()
    os._exit(0 if success else 1)
