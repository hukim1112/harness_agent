"""
tests/test_mission01.py

🎯 Mission 01 자동화 검증 스크립트 (ACI 도구 설계 & Chatbot 바인딩 검증)
1. app/tools/custom_tools.py의 필수 도구(roll_dice) 및 CUSTOM_TOOLS 레지스트리 확인
2. roll_dice의 ACI 스키마 계약 검증 (설명/경계, 인자 제약, 에러 계약)
3. roll_dice 단위 실행 검증 (정상 반환, 컨텍스트 제한 요약, 오류 피드백)
4. [Optional] CUSTOM_TOOLS에 추가된 자유 커스텀 도구의 범용 ACI 계약 검증
5. app/agents/chatbot/agent.py의 CUSTOM_TOOLS 바인딩 및 create_agent 빌드 검증

실행 방법:
  python tests/test_mission01.py
"""

import asyncio
import os
import sys
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

# 프로젝트 루트 경로 등록
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

_CONSTRAINT_KEYS = frozenset({
    "enum",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
})


def _call_tool(tool_obj: BaseTool, args: dict[str, Any]) -> ToolMessage:
    """create_agent와 동일한 LangGraph ToolNode 경로로 도구를 호출하여 ToolMessage를 반환합니다."""
    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode([tool_obj]))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    app = graph.compile()
    res = app.invoke({
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": tool_obj.name, "args": args, "id": "call_mission01"}],
            )
        ]
    })
    return res["messages"][-1]


def _has_schema_constraint(schema_node: Any) -> bool:
    """JSON Schema 노드(anyOf/oneOf/items 포함)에 제약 조건 키워드가 선언되어 있는지 확인합니다."""
    if not isinstance(schema_node, dict):
        return False
    if any(k in schema_node for k in _CONSTRAINT_KEYS):
        return True
    for nested_key in ("anyOf", "oneOf", "allOf"):
        nested = schema_node.get(nested_key)
        if isinstance(nested, list) and any(_has_schema_constraint(item) for item in nested):
            return True
    if "items" in schema_node and _has_schema_constraint(schema_node["items"]):
        return True
    return False


def _verify_aci_contract(tool_obj: Any, require_constraints: bool = True) -> bool:
    """도구가 ACI 4대 계약(스키마/설명/제약/에러핸들링)을 만족하는지 검증합니다."""
    name = getattr(tool_obj, "name", repr(tool_obj))
    assert isinstance(tool_obj, BaseTool), f"❌ '{name}'은 유효한 LangChain Tool(@tool)이 아닙니다."

    assert bool(getattr(tool_obj, "handle_tool_error", False)), (
        f"❌ '{name}'에 handle_tool_error=True가 설정되지 않았습니다.\n"
        f"   {name}.handle_tool_error = True를 설정하세요."
    )

    schema = convert_to_openai_tool(tool_obj)
    assert schema.get("type") == "function", f"❌ '{name}'의 OpenAI 도구 스키마 형식이 올바르지 않습니다."
    fn = schema["function"]
    desc = fn.get("description", "")

    assert len(desc.strip()) >= 30, f"❌ '{name}'의 도구 설명이 너무 짧습니다(30자 이상 작성 권장)."
    assert "Args:" not in desc, (
        f"❌ '{name}' 설명에 'Args:' 섹션이 중복 노출되었습니다. "
        "BaseModel(args_schema)의 Field(description=...)로 인자 설명을 분리하세요."
    )
    assert "Returns:" not in desc, f"❌ '{name}' 설명에 'Returns:' 섹션을 중복 작성하지 마세요."
    assert "Usage:" in desc, (
        f"❌ '{name}' 설명에 'Usage:' 섹션(호출 조건 및 비사용 경계)을 명시하세요."
    )

    props = fn.get("parameters", {}).get("properties", {})
    assert props, f"❌ '{name}'에 입력 파라미터 스키마가 정의되지 않았습니다."
    for param_name, param_schema in props.items():
        assert param_schema.get("description", "").strip(), (
            f"❌ '{name}.{param_name}' 파라미터에 Field(description=...)가 비어 있습니다."
        )

    has_any_constraint = any(_has_schema_constraint(p) for p in props.values())
    if require_constraints:
        assert has_any_constraint, (
            f"❌ '{name}' 파라미터에 스키마 제약(Field(ge/le/min_length) 또는 Literal[...])이 없습니다."
        )
    return has_any_constraint


async def run_mission01_test():
    print("=" * 70)
    print("🧪 [Mission 01] ACI 커스텀 도구 설계 & Chatbot 바인딩 검증 시작")
    print("=" * 70)

    # 1. custom_tools 모듈 및 도구 정의/레지스트리 검증
    try:
        from app.tools import custom_tools
    except ImportError as e:
        print(f"❌ [FAIL] app.tools.custom_tools 임포트 실패: {e}")
        return False

    assert hasattr(custom_tools, "roll_dice"), (
        "❌ app/tools/custom_tools.py에 필수 도구 'roll_dice'가 구현되지 않았습니다."
    )
    assert hasattr(custom_tools, "CUSTOM_TOOLS") and isinstance(
        custom_tools.CUSTOM_TOOLS, (list, tuple)
    ), "❌ app/tools/custom_tools.py에 'CUSTOM_TOOLS' 리스트가 정의되지 않았습니다."

    custom_names = {getattr(t, "name", "") for t in custom_tools.CUSTOM_TOOLS}
    assert "roll_dice" in custom_names, (
        "❌ app/tools/custom_tools.py의 CUSTOM_TOOLS 리스트에 'roll_dice'를 등록하세요."
    )
    print(f"  ✅ Test 1 통과: custom_tools.py 정의 및 CUSTOM_TOOLS 등록 확인 ({len(custom_tools.CUSTOM_TOOLS)}종)")

    # 2. roll_dice ACI 스키마 계약 검증
    dice_tool = custom_tools.roll_dice
    _verify_aci_contract(dice_tool, require_constraints=True)

    dice_props = convert_to_openai_tool(dice_tool)["function"]["parameters"]["properties"]
    assert "num_dice" in dice_props, "❌ roll_dice에 'num_dice' 파라미터가 없습니다."
    num_schema = dice_props["num_dice"]
    assert num_schema.get("minimum") == 1 and 10 <= num_schema.get("maximum", 0) <= 100, (
        f"❌ roll_dice.num_dice 범위 제약(ge=1, le=100)이 올바르지 않습니다: {num_schema}"
    )

    assert "sides" in dice_props, "❌ roll_dice에 'sides' 파라미터가 없습니다."
    sides_schema = dice_props["sides"]
    assert "enum" in sides_schema or sides_schema.get("minimum", 0) >= 2, (
        f"❌ roll_dice.sides에 허용 면 수 제약(Literal[...] 또는 ge>=2)이 없습니다: {sides_schema}"
    )
    print("  ✅ Test 2 통과: roll_dice ACI 스키마(설명/경계·제약조건·에러계약) 검증 완료")

    # 3. roll_dice 단위 실행: 정상 / 컨텍스트 제한 / 오류 피드백
    ok_msg = _call_tool(dice_tool, {"num_dice": 2, "sides": 6})
    assert isinstance(ok_msg, ToolMessage) and ok_msg.status == "success", (
        f"❌ roll_dice 정상 호출이 실패했습니다: {ok_msg}"
    )
    ok_text = str(ok_msg.content)
    assert any(tok in ok_text for tok in ("주사위", "Dice", "합계", "Total", "[")), (
        f"❌ roll_dice 정상 결과가 예상 포맷과 다릅니다: {ok_text}"
    )

    bulk_msg = _call_tool(dice_tool, {"num_dice": 50, "sides": 6})
    assert isinstance(bulk_msg, ToolMessage) and bulk_msg.status == "success", (
        f"❌ roll_dice 대량 호출(50개)이 실패했습니다: {bulk_msg}"
    )
    bulk_text = str(bulk_msg.content)
    assert len(bulk_text) < 500 and bulk_text.count(",") < 30, (
        f"❌ roll_dice 50개 호출 시 개별 목록을 그대로 출력해 컨텍스트 보호가 작동하지 않았습니다: {bulk_text}"
    )
    assert any(tok in bulk_text for tok in ("요약", "생략", "컨텍스트", "평균", "분포")), (
        f"❌ roll_dice 50개 호출 시 통계 요약 안내가 포함되어야 합니다: {bulk_text}"
    )

    for bad_args in (
        {"num_dice": 0, "sides": 6},
        {"num_dice": 200, "sides": 6},
        {"num_dice": 2, "sides": 0},
        {"num_dice": 2, "sides": 7},
    ):
        err_msg = _call_tool(dice_tool, bad_args)
        assert isinstance(err_msg, ToolMessage) and err_msg.status == "error", (
            f"❌ 잘못된 입력 {bad_args}에 대해 ToolMessage(status='error')를 반환해야 합니다: {err_msg}"
        )
        assert len(str(err_msg.content).strip()) > 0, "❌ 오류 피드백 내용이 비어 있습니다."

    print("  ✅ Test 3 통과: roll_dice 정상 실행 · 컨텍스트 제한(50개 요약) · 오류 피드백(status='error') 검증 완료")

    # 4. [Optional] 사용자가 자유롭게 추가한 커스텀 도구의 범용 ACI 검증
    extra_tools = [t for t in custom_tools.CUSTOM_TOOLS if getattr(t, "name", "") != "roll_dice"]
    if extra_tools:
        for extra in extra_tools:
            has_c = _verify_aci_contract(extra, require_constraints=False)
            c_note = "제약조건 포함" if has_c else "💡 팁: Field(ge/le) 또는 Literal 제약을 추가하면 더 안전해집니다"
            print(f"  ✅ Test 4 (선택) 통과: 자유 도구 '{extra.name}' ACI 계약 확인 ({c_note})")
    else:
        print("  ℹ️ Test 4 (선택): 추가 자유 도구 없음 — 필수 roll_dice 기준으로 통과합니다.")

    # 5. chatbot 에이전트 바인딩 검증
    from app.agents import chatbot
    from tests.agent_inspector import close_agent_resources, extract_agent_tools

    try:
        agent = await chatbot.create_agent_executor()
    except Exception as e:
        print(f"❌ [FAIL] chatbot.create_agent_executor 실행 중 에러 발생: {e}")
        return False

    try:
        tools = extract_agent_tools(agent)
        tool_names = {getattr(t, "name", "") for t in tools}

        for registered in custom_tools.CUSTOM_TOOLS:
            r_name = getattr(registered, "name", "")
            assert r_name in tool_names, (
                f"❌ chatbot 에이전트에 '{r_name}' 도구가 바인딩되지 않았습니다.\n"
                "   app/agents/chatbot/agent.py의 active_tools에 list(CUSTOM_TOOLS)를 추가하세요."
            )
        print(f"  ✅ Test 5 통과: chatbot 에이전트에 CUSTOM_TOOLS 바인딩 확인 (총 {len(tools)}종)")
    finally:
        await close_agent_resources(agent)

    print("\n" + "=" * 70)
    print("🎉 [Mission 01] ACI 커스텀 도구 설계 및 챗봇 결합 검증 100% 통과!")
    print("   이제 Chainlit UI에서 도구를 호출하고 컨텍스트 제한 및 오류 피드백을 체험하세요.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    import traceback

    success = False
    try:
        success = asyncio.run(run_mission01_test())
    except AssertionError as e:
        print(f"\n{e}")
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0 if success else 1)
