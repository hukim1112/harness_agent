"""
tests/test_mission04.py

🎯 Mission 04 자동화 검증 스크립트: Progressive Skills 동적 확장 · User Context 카탈로그 · 양방향 Skill Delta
1. skills/ 디렉토리에 금융 전문 스킬 탑재 및 SKILL.md 규격 확인
2. SkillPromptBuilder의 Frontmatter 스캔 및 구조화된 스킬 목록/카탈로그 생성 검증
3. main_agent의 User Context(# skillCatalog) 내 금융 스킬 주입 + Static SystemMessage 불변 검증
4. Progressive Skill 실행 필수 도구(file_read, bash_command) 바인딩 검증
5. 세션 중 스킬 추가/제거 시 양방향 skill_delta 알림 및 프리픽스 캐시 유지 시각화

실행 방법:
  python tests/test_mission04.py
"""

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)


REQUIRED_FINANCIAL_SKILLS = [
    "pykrx-korean-market",
    "yfinance-market-data",
    "fred-macro-economics",
    "portfolio-risk-quant",
    "technical-analysis-indicators",
]


async def run_mission04_test():
    print("=" * 70)
    print("🧪 [Mission 04] Progressive Skills 동적 확장 · 카탈로그 · Skill Delta 검증 시작")
    print("=" * 70)

    # 1. main_agent 내장 skills/ 디렉토리 내 금융 스킬 존재 확인
    skills_rel = "app/agents/main_agent/skills"
    skills_dir = os.path.join(project_root, *skills_rel.split("/"))
    assert os.path.exists(skills_dir), f"❌ {skills_rel} 디렉토리가 존재하지 않습니다."

    installed_skills = [
        d for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d))
    ]

    missing = [s for s in REQUIRED_FINANCIAL_SKILLS if s not in installed_skills]
    assert not missing, (
        f"❌ {skills_rel}/ 디렉토리에 필수 금융 스킬이 누락되었습니다: {missing}\n"
        f"   💡 artifacts/skills_pool/ 에서 {skills_rel}/ 로 스킬을 복사하세요:\n"
        f"   명령어: cp -r artifacts/skills_pool/* {skills_rel}/"
    )

    for s in REQUIRED_FINANCIAL_SKILLS:
        skill_md = os.path.join(skills_dir, s, "SKILL.md")
        assert os.path.exists(skill_md), f"❌ '{s}' 스킬 폴더에 SKILL.md 파일이 없습니다: {skill_md}"

    print(f"  ✅ Test 1 통과: {skills_rel}/ 내 금융 전문 스킬 및 SKILL.md 확인 (현재 탑재: 총 {len(installed_skills)}종)")

    # 2. SkillPromptBuilder 스캔 동작 검증
    from app.middleware.prompt.skill_builder import SkillPromptBuilder

    builder = SkillPromptBuilder(skills_dirs=[skills_dir], guidelines_path=os.path.join(skills_dir, "SKILL.md"))
    listed_names = {s["name"] for s in builder.list_skills()}
    catalog_text = builder.build_catalog()

    for s in REQUIRED_FINANCIAL_SKILLS:
        assert s in listed_names and s in catalog_text, f"❌ SkillPromptBuilder 카탈로그에 '{s}' 스킬이 스캔되지 않았습니다."
    print(f"  ✅ Test 2 통과: SkillPromptBuilder Frontmatter 스캔 완료 ({len(listed_names)}종 인덱싱)")

    # 3. main_agent 생성 및 User Context(# skillCatalog) 주입 + Static SystemMessage 순수성 검증
    from langchain_core.messages import AIMessage, HumanMessage
    from app.agents import main_agent
    from app.context import AgentContext
    from app.middleware.prompt import (
        PromptAssembler,
        PromptAssemblerMiddleware,
        create_prompt_assembler_middleware,
        simulate_turn,
    )
    from app.middleware.prompt.prompt_assembler import SKILL_ADDED_KEY, SKILL_REMOVED_KEY
    from app.utils.message_markers import ORIGIN_SKILL_DELTA, ORIGIN_USER_CONTEXT, message_origin
    from tests.agent_inspector import (
        close_agent_resources,
        extract_agent_tools,
        extract_prompt_assembler,
        find_agent_middleware,
    )

    agent = await main_agent.create_agent_executor()
    assert agent is not None, "❌ main_agent 생성 실패"

    assembler = extract_prompt_assembler(agent)
    prompt_mw = find_agent_middleware(agent, PromptAssemblerMiddleware)
    assert assembler is not None and prompt_mw is not None, "❌ main_agent에 PromptAssemblerMiddleware가 탑재되지 않았습니다."

    static_prompt = assembler.build_static_prompt()
    for s in REQUIRED_FINANCIAL_SKILLS:
        assert s not in static_prompt, f"❌ 정적 SystemMessage에 동적 스킬 이름('{s}')이 들어가면 캐시가 깨집니다."

    tools = extract_agent_tools(agent)
    state_main = {"messages": [HumanMessage(content="삼성전자 최근 시세를 분석해줘.", id="m04_main_u1")]}
    ctx_main = AgentContext(user_id="default", session_id="mission04_verify")
    out_main = simulate_turn(prompt_mw, state_main, "Mission 04 — main_agent Turn 1", tools=tools, context=ctx_main)
    assert message_origin(out_main.messages[1]) == ORIGIN_USER_CONTEXT
    for s in REQUIRED_FINANCIAL_SKILLS:
        assert s in out_main.messages[1].content, f"❌ main_agent User Context(# skillCatalog)에 '{s}' 스킬이 주입되지 않았습니다."
    print("  ✅ Test 3 통과: Static SystemMessage 불변 + User Context(# skillCatalog) 금융 스킬 자동 주입 확인")

    # 4. Progressive Skill 실행 필수 도구 확인 (file_read, bash_command)
    tool_names = {getattr(t, "name", "") for t in tools}
    assert "file_read" in tool_names, "❌ main_agent에 'file_read' 도구가 바인딩되지 않았습니다."
    assert "bash_command" in tool_names, "❌ main_agent에 'bash_command' 도구가 바인딩되지 않았습니다."
    print("  ✅ Test 4 통과: Progressive Skill 실행 필수 도구 바인딩 확인 (file_read, bash_command)")

    await close_agent_resources(agent)

    # 5. 세션 중 스킬 추가/제거 양방향 Skill Delta 시뮬레이션 (임시 복사본에서 실행)
    with tempfile.TemporaryDirectory(prefix="m04_skill_delta_") as tmpdir:
        tmp_skills = Path(tmpdir) / "skills"
        shutil.copytree(skills_dir, tmp_skills)
        demo_builder = SkillPromptBuilder(
            skills_dirs=[str(tmp_skills)],
            guidelines_path=str(tmp_skills / "SKILL.md"),
        )
        demo_assembler = PromptAssembler(
            system_prompt=assembler.system_prompt,
            skill_guidelines=demo_builder.load_guidelines,
            skill_provider=demo_builder.list_skills,
        )
        demo_mw = create_prompt_assembler_middleware(demo_assembler)
        demo_ctx = AgentContext(user_id="default", session_id="mission04_delta_demo")
        demo_state = {"messages": [HumanMessage(content="금융 스킬 목록 확인", id="d1")]}

        out_t1 = simulate_turn(demo_mw, demo_state, "Skill Delta 시뮬레이션 — Turn 1 (초기 카탈로그)", tools=tools, context=demo_ctx)

        # Turn 2: 임시 스킬 1종 추가 + 기존 스킬 1종 제거
        new_skill_dir = tmp_skills / "temp-fx-arbitrage"
        new_skill_dir.mkdir(parents=True, exist_ok=True)
        (new_skill_dir / "SKILL.md").write_text(
            "---\nname: temp-fx-arbitrage\ndescription: 세션 중 새로 설치된 FX 차익거래 스킬\n---\n# Temp FX\n",
            encoding="utf-8",
        )
        removed_target = tmp_skills / "alpha-vantage-finance"
        if removed_target.exists():
            shutil.rmtree(removed_target)

        demo_state["messages"] += [
            AIMessage(content="현재 금융 스킬 12종이 등록되어 있습니다.", id="da1"),
            HumanMessage(content="방금 스킬을 교체했어. 최신 목록으로 작업하자.", id="d2"),
        ]
        print("\n🎨 [실물 시각화] 세션 중 스킬 추가(+temp-fx-arbitrage)·제거(-alpha-vantage-finance) Delta 주입")
        out_t2 = simulate_turn(
            demo_mw,
            demo_state,
            "Skill Delta 시뮬레이션 — Turn 2 (양방향 Delta + 앞단 100% 캐시 유지)",
            prev_messages=out_t1.messages,
            tools=tools,
            context=demo_ctx,
        )
        delta_msg = out_t2.messages[-1]
        assert message_origin(delta_msg) == ORIGIN_SKILL_DELTA
        assert "temp-fx-arbitrage" in delta_msg.additional_kwargs[SKILL_ADDED_KEY]
        assert "alpha-vantage-finance" in delta_msg.additional_kwargs[SKILL_REMOVED_KEY]
        assert out_t2.messages[0].content == out_t1.messages[0].content
        assert out_t2.messages[1].content == out_t1.messages[1].content
        print("  ✅ Test 5 통과: 양방향 Skill Delta(+추가/-제거) 발행 및 앞단 프리픽스 100% 보존 확인")

    print("\n🎉 [Mission 04] Progressive Skills 동적 확장 · 카탈로그 · Skill Delta 검증 100% 통과!")
    return True


if __name__ == "__main__":
    import traceback

    success = False
    try:
        success = asyncio.run(run_mission04_test())
    except AssertionError as e:
        print(f"\n{e}")
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0 if success else 1)
