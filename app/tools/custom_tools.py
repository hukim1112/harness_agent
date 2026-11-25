"""
app/tools/custom_tools.py

🎯 Mission 01: ACI(Agent-Computer Interface) 철학 기반 커스텀 도구 기준 완성본
좋은 도구의 4대 요소(정답 반환·컨텍스트 제한 / 제약 사항·안정성 / 예외 처리·오류 피드백 / 설명·인자 정의)를
적용한 필수 도구 `roll_dice`를 제공합니다.

[Optional] 스스로 만들고 싶은 나만의 커스텀 도구를 추가했다면
`<도구>.handle_tool_error = True`를 설정한 뒤 하단의 `CUSTOM_TOOLS` 리스트에 함께 등록하세요.
"""

import random
from collections import Counter

from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field

_ALLOWED_SIDES = (4, 6, 8, 10, 12, 20, 100)
_DETAILED_ROLL_LIMIT = 20


class RollDiceInput(BaseModel):
    num_dice: int = Field(
        default=1,
        ge=1,
        le=100,
        description=(
            "굴릴 주사위 개수 (1~100, 기본값: 1). "
            "20개를 초과하면 컨텍스트 보호를 위해 개별 눈 목록 대신 통계 요약만 반환합니다."
        ),
    )
    sides: int = Field(
        default=6,
        ge=4,
        le=100,
        description="주사위의 면 수 (표준 다면체: 4, 6, 8, 10, 12, 20, 100 중 선택, 기본값: 6).",
    )


@tool(args_schema=RollDiceInput)
def roll_dice(num_dice: int = 1, sides: int = 6) -> str:
    """표준 다면체 주사위를 굴려 무작위 결과와 통계를 반환합니다.

    Usage:
    - 사용자가 주사위 굴리기, 보드게임/TRPG 판정(d4~d100), 간단한 확률 추첨을 요청할 때 호출하세요.
    - 20개 이하는 개별 눈 목록과 통계를, 21~100개는 컨텍스트 창 보호를 위해 통계 요약만 반환합니다.
    - When NOT to use: 표준 다면체 외 임의 범위 난수(예: 1~45 로또), 암호학적 난수, 100회 초과 대규모 시뮬레이션은 bash_command(Python)를 사용하세요.
    """
    if num_dice < 1 or num_dice > 100:
        raise ToolException(
            "RollDice Error: 'num_dice'는 1~100 범위여야 합니다. "
            "100회를 초과하는 시뮬레이션은 bash_command(Python)를 사용하세요."
        )
    if sides not in _ALLOWED_SIDES:
        raise ToolException(
            f"RollDice Error: 지원하지 않는 면 수(sides={sides})입니다. "
            f"허용 값 {list(_ALLOWED_SIDES)} 중 하나를 선택해 다시 호출하세요."
        )

    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    total = sum(rolls)
    avg = total / num_dice
    low = min(rolls)
    high = max(rolls)

    if num_dice <= _DETAILED_ROLL_LIMIT:
        return (
            f"🎲 주사위 {num_dice}개(d{sides}) 결과: {rolls} | "
            f"합계: {total} (평균: {avg:.2f}, 최소: {low}, 최대: {high})"
        )

    counts = Counter(rolls)
    if sides <= 20:
        dist_note = "눈 분포: " + ", ".join(f"{k}:{counts[k]}" for k in sorted(counts))
    else:
        top5 = ", ".join(f"{k}({c}회)" for k, c in counts.most_common(5))
        dist_note = f"고유 눈 {len(counts)}종, 최빈값 TOP 5: {top5}"

    return (
        f"🎲 주사위 {num_dice}개(d{sides}) 요약 결과 "
        f"(컨텍스트 보호: {_DETAILED_ROLL_LIMIT}개 초과로 개별 눈 목록 생략) | "
        f"합계: {total} (평균: {avg:.2f}, 최소: {low}, 최대: {high}) | {dist_note}"
    )


roll_dice.handle_tool_error = True

# [Optional] 스스로 만들고 싶은 나만의 ACI 도구를 추가했다면
# `<도구>.handle_tool_error = True`를 설정한 뒤 아래 CUSTOM_TOOLS 리스트에 함께 등록하세요.
CUSTOM_TOOLS = [roll_dice]

__all__ = [
    "roll_dice",
    "CUSTOM_TOOLS",
]
