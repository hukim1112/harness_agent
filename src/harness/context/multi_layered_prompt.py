"""
===============================================================================
[Harness Module 02-2] MultiLayeredPrompt Agent Middleware (dynamic_prompt)
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Course Material: 2.Agent Context Engineering.ipynb (from langchain.agents.middleware)
- Middleware Hook Signature: @dynamic_prompt def (request: ModelRequest) -> str
- Architecture Notes: references/ref_02_context/architecture_notes.md

[5-Layer Prompt Stack & Caching Architecture Principle]
-------------------------------------------------------------------------------
1. 정적 영역 (Layer 1 ~ Layer 3) -> KV Cache HIT 대상
   - [L1: GLOBAL BASE]: 에이전트 페르소나 및 런타임 차등 권한/환경 지침 (dynamic_l1)
   - [L2: TOOL SPECIFICATIONS]: request.tools로부터 추출한 도구들의 JSON Schema 명세
   - [L3: LOCAL PROJECT RULES]: AGENT.md에 기술된 레포지토리 로컬 행동 강령
   - 이 영역들은 경계선(=== DYNAMIC_BOUNDARY ===) 윗단에 고정되어 OpenAI KV Cache에 영구 적치됩니다.

2. 동적 환경 영역 (Layer 4) -> boundary 아래 위치 (Uncached)
   - [L4: DYNAMIC_WORKING_CONTEXT]: 운영체제(OS), 타임스탬프, 턴수, 툴 히스토리 등 매 호출마다 
     완전히 새로 갱신되는 런타임 환경 데이터를 실시간 조립하여 주입합니다.
   - 변동성이 극심한 L4가 경계선 아래로 격리됨으로써 상단 L1~L3의 정적 캐시 오염을 완벽히 방지합니다.

3. 사용자 최종 입력 (Layer 5) -> 프레임워크 자동 연동 (Excluded from System Prompt)
   - [L5: DYNAMIC_USER_TASK]: 사용자가 입력한 최종 태스크(질문)는 에이전트 루프가 격발될 때 
     메시지 리스트(messages)의 가장 마지막 HumanMessage 객체로 자연스럽게 전달됩니다.
   - 따라서 미들웨어(System Prompt를 반환하는 @dynamic_prompt 훅) 본문 안에 최종 입력을 중복 
     기재하지 않고 제외함으로써, 랭체인 프레임워크의 표준 메시지 구조와 유기적으로 연합합니다.
===============================================================================
"""

import os
import json
from langchain.agents.middleware import dynamic_prompt, ModelRequest
from harness.context.prompt_caching import MultiLayeredPrompt



@dynamic_prompt
def multi_layered_prompt_middleware(request: ModelRequest) -> str:
    """에이전트 LLM 호출 직전에 격발되어, gpt_system_prompt.md와 AGENT.md, 
    그리고 runtime context/store 및 도구(request.tools) 명세를 결합하여
    5계층 동적 프롬프트를 완성한 후 최종 System Prompt 문자열을 반환하는 교안 규격 미들웨어.
    """
    ctx = request.runtime.context
    
    # 1. runtime.context로부터 동적인 L1 지침(역할, 환경, 세션 등) 획득 및 조립
    user_role = getattr(ctx, "user_role", "viewer")
    deployment_env = getattr(ctx, "deployment_env", "staging")
    user_id = getattr(ctx, "user_id", "guest")
    
    dynamic_l1 = (
        f"You are operating with user_role='{user_role}' on session_user_id='{user_id}'.\n"
        f"The current deployment environment is: {deployment_env}."
    )

    # 2. Layer 4 동적 환경 변수 조합 (OS, 실시간 일시, 턴수, 도구 궤적 등)
    import platform
    import datetime
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os_info = f"{platform.system()} {platform.release()}"
    turn_count = len(request.messages) // 2
    
    dynamic_trajectory = (
        f"- Target OS: {os_info}\n"
        f"- Current Timestamp: {current_time}\n"
        f"- Conversation Turn: {turn_count} active."
    )
    if request.state and "intermediate_steps" in request.state:
        steps_len = len(request.state["intermediate_steps"])
        dynamic_trajectory += f"\n- Executed Tool Steps: {steps_len}."

    # 3. MultiLayeredPrompt 빌더 격발
    prompt_builder = MultiLayeredPrompt(
        tools=request.tools,
        custom_dynamic_l1=dynamic_l1,
        prompt_file_path="prompts/gpt_system_prompt.md",
        rules_file_path="prompts/AGENT.md"
    )
    
    # L1~L4 가 조립된 최종 시스템 프롬프트 문자열 획득
    new_system_prompt = prompt_builder.assemble_layered_system_prompt(dynamic_context=dynamic_trajectory)
    return new_system_prompt
