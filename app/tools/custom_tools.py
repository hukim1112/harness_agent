"""
app/tools/custom_tools.py

🎯 Mission 01: ACI(Agent-Computer Interface) 철학 기반 커스텀 도구 작성하기
missions/01_mission_add_custom_tool.md 가이드를 참고하여,
모델이 컴퓨터와 안전하고 효율적으로 상호작용할 수 있는 ACI 커스텀 도구를 작성하세요.

[좋은 도구의 4대 설계 원칙 (ACI)]
1. 정답 반환 & 컨텍스트 제한: 구조화된 결과를 반환하되, 대량 결과는 요약/절단하여 컨텍스트 오염 방지
2. 제약 사항 & 안정성 (Poka-yoke): Pydantic `BaseModel` + `Field(ge/le)` · `Literal[...]`로 잘못된 호출 사전 차단
3. 예외 처리 & 오류 피드백: `ToolException` + `<도구>.handle_tool_error = True`로 크래시 대신 수정 힌트 반환
4. 설명 & 인자 정의의 조화: `Usage:`와 `When NOT to use:` 경계를 명시하고 `Args:` 중복은 피함
"""

import random
from collections import Counter
from typing import Literal

from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------------
# TODO ① [필수] 주사위 굴리기 도구 `roll_dice`를 ACI 원칙에 맞게 구현하세요.
#
# ⚠️ [주의] 자동화 검증 스크립트(test_mission01.py)와 이후 미션(Mission 03, 05, 07, 08)에서
# `roll_dice`와 `CUSTOM_TOOLS`를 직접 참조하므로 반드시 아래 규격으로 구현해야 합니다:
#   - 스키마(RollDiceInput):
#       * num_dice: int = Field(default=1, ge=1, le=100, description="...")
#       * sides: int = Field(default=6, ge=4, le=100, description="...")
#   - 컨텍스트 제한: 20개 이하는 개별 눈 목록+통계, 21~100개는 개별 목록 생략 후 통계 요약만 반환
#   - 오류 피드백: 잘못된 입력 시 ToolException 발생 + roll_dice.handle_tool_error = True 설정
# -------------------------------------------------------------------------------

# class RollDiceInput(BaseModel):
#     num_dice: int = Field(default=1, ge=1, le=100, description="...")
#     sides: int = Field(default=6, ge=4, le=100, description="...")
#
#
# @tool(args_schema=RollDiceInput)
# def roll_dice(num_dice: int = 1, sides: int = 6) -> str:
#     """표준 다면체 주사위를 굴려 무작위 결과와 통계를 반환합니다.
#
#     Usage:
#     - ...
#     - When NOT to use: ...
#     """
#     ...
#
# roll_dice.handle_tool_error = True


# -------------------------------------------------------------------------------
# TODO ② [Optional] 스스로 만들고 싶은 나만의 커스텀 도구를 자유롭게 추가해 보세요!
#
# 챗봇에게 쥐어주고 싶은 도구가 있다면 ACI 4대 원칙(Pydantic 스키마·제약 조건·컨텍스트 제한·
# ToolException + `<도구>.handle_tool_error = True`·Usage/When NOT to use 설명)에 맞춰 구현한 뒤
# 아래 `CUSTOM_TOOLS` 리스트에 함께 등록하고 Chainlit UI에서 대화로 트리거링해 보세요.
# -------------------------------------------------------------------------------


# 구현 완료 후 작성한 도구 객체를 CUSTOM_TOOLS 리스트에 등록하세요. (예: [roll_dice])
CUSTOM_TOOLS = []

__all__ = [
    "CUSTOM_TOOLS",
]
