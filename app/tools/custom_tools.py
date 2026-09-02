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
# TODO: 나만의 커스텀 도구를 아래에 작성하세요.
# 예시 1) 주사위 굴리기 (roll_dice)
# 예시 2) 환율 계산기 (convert_currency)
# 예시 3) 로또 번호 추천, 가상 코인 던지기, 간단 메모 등 자유롭게 작성 가능!
# -------------------------------------------------------------------------------

# @tool(parse_docstring=True)
# def my_custom_tool(param: str) -> str:
#     """도구에 대한 설명문 및 호출 조건을 작성하세요.
#     
#     Args:
#         param: 파라미터 설명
#     """
#     return "도구 실행 결과"
