"""
app/tools/custom_tools.py

🎯 Mission 01: 나만의 커스텀 도구(Custom Tool) 작성하기
missions/01_mission_add_custom_tool.md 가이드를 참고하여, 
LangChain의 @tool 데코레이터를 이용해 에이전트가 호출할 수 있는 도구 함수를 작성하세요.

[핵심 팁]
1. @tool(parse_docstring=True)를 적용합니다.
2. Docstring의 첫 줄에는 도구의 목적을 명확히 작성합니다.
3. 언제 이 도구를 호출해야 하는지 '트리거 조건(호출 규칙)'을 반드시 Docstring에 명시합니다.
4. Args: 섹션에 각 파라미터의 타입과 설명을 작성합니다.
"""

import random
from langchain_core.tools import tool


# -------------------------------------------------------------------------------
# TODO: 필수 커스텀 도구 2종(roll_dice, convert_currency)을 아래에 작성하세요.
#
# ⚠️ [주의] 자동화 검증 스크립트(test_mission01.py, test_mission05.py, test_mission07.py, test_final.py)에서
# 다음 두 함수 이름과 인자 규격을 직접 호출하여 검증하므로 2가지 모두 필수로 구현해야 합니다:
#   1) 주사위 굴리기: roll_dice(num_dice: int = 1, sides: int = 6) -> str
#   2) 환율 계산기  : convert_currency(amount: float, from_currency: str = "USD", to_currency: str = "KRW") -> str
# (위 2가지를 작성한 뒤, 로또 번호 추천 등 나만의 추가 도구를 더 만들어도 좋습니다!)
# -------------------------------------------------------------------------------

# @tool(parse_docstring=True)
# def roll_dice(num_dice: int = 1, sides: int = 6) -> str:
#     """도구에 대한 설명문 및 호출 조건을 작성하세요.
#
#     Args:
#         num_dice: 굴릴 주사위 개수 (기본값: 1, 최대: 10)
#         sides: 주사위의 면 수 (기본값: 6, 예: 6, 12, 20)
#     """
#     return "도구 실행 결과"
