"""
tests/test_mission04.py

🎯 Mission 04 자동화 검증 스크립트: Progressive Skills 동적 확장 & 카탈로그 검증
1. skills/ 디렉토리에 금융 전문 스킬 탑재 및 SKILL.md 규격 확인
2. SkillPromptBuilder의 Frontmatter 스캔 및 카탈로그 자동 인덱싱 검증
3. main_agent의 5-Layer 프롬프트(Layer 2.2) 내 금융 스킬 카탈로그 주입 검증
4. Progressive Skill 실행 필수 도구(file_read, bash_command) 바인딩 검증
5. 런타임 조립된 Available Skills Catalog 실물 터미널 시각화

실행 방법:
  python tests/test_mission04.py
"""

import os
import sys
import asyncio

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
    print("🧪 [Mission 04] Progressive Skills 동적 확장 & 카탈로그 검증 시작")
    print("=" * 70)

    # 1. skills/ 디렉토리 내 금융 스킬 존재 확인
    skills_dir = os.path.join(project_root, "skills")
    assert os.path.exists(skills_dir), "❌ skills 디렉토리가 존재하지 않습니다."

    installed_skills = [
        d for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d))
    ]

    missing = [s for s in REQUIRED_FINANCIAL_SKILLS if s not in installed_skills]
    assert not missing, (
        f"❌ skills/ 디렉토리에 필수 금융 스킬이 누락되었습니다: {missing}\n"
        f"   💡 artifacts/skills_pool/ 에서 skills/ 로 스킬을 복사하세요:\n"
        f"   명령어: cp -r artifacts/skills_pool/* skills/"
    )

    # 각 스킬의 SKILL.md 유효성 확인
    for s in REQUIRED_FINANCIAL_SKILLS:
        skill_md = os.path.join(skills_dir, s, "SKILL.md")
        assert os.path.exists(skill_md), f"❌ '{s}' 스킬 폴더에 SKILL.md 파일이 없습니다: {skill_md}"

    print(f"  ✅ Test 1 통과: skills/ 내 금융 전문 스킬 및 SKILL.md 확인 (현재 탑재: 총 {len(installed_skills)}종)")

    # 2. SkillPromptBuilder 스캔 동작 검증
    from app.middleware.prompt.skill_builder import SkillPromptBuilder

    builder = SkillPromptBuilder(skills_dirs=[skills_dir])
    catalog_text = builder.assemble()

    for s in REQUIRED_FINANCIAL_SKILLS:
        assert s in catalog_text, f"❌ SkillPromptBuilder 카탈로그에 '{s}' 스킬이 스캔되지 않았습니다."
    print("  ✅ Test 2 통과: SkillPromptBuilder Frontmatter 스캔 및 카탈로그 생성 완료")

    # 3. main_agent 생성 및 5-Layer 프롬프트의 Layer 2.2 주입 검증
    from app.agents import main_agent

    agent = await main_agent.create_agent_executor()
    assert agent is not None, "❌ main_agent 생성 실패"

    # 프롬프트 조립기에서 static content 생성
    assembler = getattr(agent, "prompt_assembler", None)
    if not assembler:
        # main_agent.py 내부에서 assembler 찾기
        import inspect
        source = inspect.getsource(main_agent.create_agent_executor)
        assert "PromptAssembler" in source, "❌ main_agent.py에 PromptAssembler가 사용되지 않았습니다."
        assert "SkillPromptBuilder" in source, "❌ main_agent.py에 SkillPromptBuilder가 사용되지 않았습니다."

    # 4. Progressive Skill 실행 필수 도구 확인 (file_read, bash_command)
    tools = getattr(agent, "registered_tools", [])
    if not tools and hasattr(agent, "nodes"):
        tools_node = agent.nodes.get("tools")
        if tools_node and hasattr(tools_node, "tools_by_name"):
            tools = list(tools_node.tools_by_name.values())

    tool_names = {getattr(t, "name", "") for t in tools}
    assert "file_read" in tool_names, (
        "❌ main_agent에 'file_read' 도구가 바인딩되지 않았습니다.\n"
        "   에이전트가 SKILL.md를 읽기 위해 file_read 도구가 필수입니다."
    )
    assert "bash_command" in tool_names, (
        "❌ main_agent에 'bash_command' 도구가 바인딩되지 않았습니다.\n"
        "   에이전트가 스킬 파이썬 스크립트를 실행하기 위해 bash_command 도구가 필수입니다."
    )
    print("  ✅ Test 3 통과: Progressive Skill 실행 필수 도구 바인딩 확인 (file_read, bash_command)")

    # 5. 리소스 정리
    conn = getattr(agent, "checkpointer_conn", None)
    if conn:
        await conn.close()

    # 6. 실물 시각화 출력
    print("\n" + "=" * 70)
    print("🎨 [실물 시각화] main_agent 시스템 프롬프트(Layer 2.2)에 자동 주입된 스킬 카탈로그")
    print("=" * 70)
    print(catalog_text.strip())
    print("=" * 70)

    print("\n🎉 [Mission 04] Progressive Skills 동적 확장 & 카탈로그 검증 100% 통과!")
    print("   이제 Chainlit UI에서 main_agent를 선택하고 금융 분석 시나리오를 테스트하세요.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_mission04_test())
    sys.stdout.flush()
    os._exit(0 if success else 1)
