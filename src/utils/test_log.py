"""
에이전트 테스트 런타임의 실시간 스트리밍 모니터링 및 전체 궤적 디버깅 전담 모듈.
"""
from typing import Dict, Any
from utils.message_utils import normalize_content

def stream_and_debug_agent(agent, inputs: Dict[str, Any], config: Dict[str, Any], agent_name: str = "ReAct 에이전트") -> Dict[str, Any]:
    """에이전트의 실행 노드 및 툴 호출을 실시간 스트리밍 로깅하고, 
    최종 완료 후 전체 궤적(Trajectory)을 pretty_print()로 정밀 덤프해주는 통합 헬퍼 함수.
    """
    print(f"🔄 [System] {agent_name} 실시간 스트리밍 구동 개시...\n")
    print("-" * 80)
    
    # 1. 실시간 스트리밍 로깅 진행
    for chunk in agent.stream(inputs, config=config):
        for node_name, state_delta in chunk.items():
            messages = state_delta.get("messages", [])
            if not messages:
                continue
                
            latest_msg = messages[-1]
            msg_type = latest_msg.__class__.__name__
            
            if msg_type == "AIMessage":
                # 툴 호출이 있는 경우
                if latest_msg.tool_calls:
                    for tool_call in latest_msg.tool_calls:
                        print(f"🤖 [Agent Thought] ➔ 도구 호출 준비 중: {tool_call['name']}({tool_call['args']})")
                # 최종 텍스트 답변이 생성된 경우
                elif latest_msg.content:
                    clean_text = normalize_content(latest_msg.content)
                    print(f"🤖 [Agent Final Answer] ➔ {clean_text[:120]}...")
                    
            elif msg_type == "ToolMessage":
                clean_obs = normalize_content(latest_msg.content)
                short_obs = clean_obs.replace("\n", " ")[:80] + "..." if len(clean_obs) > 80 else clean_obs
                print(f"🛠️  [Tool Execution] ➔ '{latest_msg.name}' 완료! 결과: {short_obs}")
                
    print("-" * 80)
    print("✅ [System] 에이전트 스트리밍 실행 완료. 전체 궤적 복원 중...\n")
    
    # 2. 최종 궤적 디버깅 출력
    print("\n" + "="*80)
    print("🔎 [TRAJECTORY DEBUGGER] 에이전트 생각 및 도구 호출 전체 로그")
    print("="*80 + "\n")
    
    final_state = agent.get_state(config)
    full_messages = final_state.values.get("messages", [])
    
    for idx, message in enumerate(full_messages):
        print(f"[{idx+1}] {message.__class__.__name__}:")
        if hasattr(message, "content"):
            message.content = normalize_content(message.content)
        message.pretty_print()
        print("-" * 50)
        
    return final_state.values


def render_pretty_prompt_stack(messages) -> None:
    """5계층 프롬프트 적층 구조와 캐시 경계선을 HTML 레이아웃으로 이쁘게 주피터에 렌더링합니다."""
    try:
        from IPython.display import display, HTML
    except ImportError:
        # 일반 CLI 터미널 환경 구동 시에는 마크다운 날것으로 콘솔 프린트
        print("\n=== 🧠 [STATIC SYSTEM PROMPT (Cached Area)] ===")
        print(messages[0].content)
        print("\n=== 🛑 [DYNAMIC BOUNDARY MARKER (KV Cache Line)] ===")
        print("\n=== ⚡ [DYNAMIC HUMAN PROMPT (Uncached Area)] ===")
        print(messages[1].content)
        return

    system_prompt = messages[0].content
    human_prompt = messages[1].content
    
    boundary_marker = "=== DYNAMIC_BOUNDARY ==="
    if boundary_marker in system_prompt:
        static_part, _ = system_prompt.split(boundary_marker, 1)
    else:
        static_part = system_prompt

    # 1. Static Part에서 Layer 1, Layer 2, Layer 3 정적 계층 분리 파싱
    # MultiLayeredPrompt가 조립 시 박아 넣는 [LAYER X] 태그를 기준으로 칼같이 자릅니다.
    l1_tag = "[LAYER 1: GLOBAL BASE & PERSONALITY]"
    l2_tag = "[LAYER 2: TOOL SPECIFICATIONS]"
    l3_tag = "[LAYER 3: LOCAL PROJECT RULES]"
    
    layer1_text = ""
    layer2_text = ""
    layer3_text = ""
    
    try:
        if l2_tag in static_part and l3_tag in static_part:
            # Layer 1 추출
            parts_l2 = static_part.split(l2_tag, 1)
            layer1_text = parts_l2[0].replace(l1_tag, "").strip()
            
            # Layer 2 및 Layer 3 추출
            rest = parts_l2[1]
            parts_l3 = rest.split(l3_tag, 1)
            layer2_text = parts_l3[0].strip()
            layer3_text = parts_l3[1].strip()
        else:
            # 구버전 프롬프트 규격 폴백 파싱
            l1_marker = "## Personality & Interpersonal Spec"
            l2_marker = "## Doing Software Engineering Tasks"
            l3_marker = "## Executing Actions with Care"
            parts_l2 = static_part.split(l2_marker, 1)
            layer1_text = parts_l2[0].replace("# [STATIC SYSTEM PROMPT: GPT-4o Production Agent Spec]", "").strip()
            rest = parts_l2[1]
            if l3_marker in rest:
                parts_l3 = rest.split(l3_marker, 1)
                layer2_text = l2_marker + "\n" + parts_l3[0].strip()
                layer3_text = l3_marker + "\n" + parts_l3[1].strip()
            else:
                layer2_text = l2_marker + "\n" + rest.strip()
                layer3_text = "N/A"
    except Exception:
        layer1_text = static_part.strip()
        layer2_text = "Tool Spec segment parsing bypassed."
        layer3_text = "Action Spec segment parsing bypassed."

    # 2. Human Part에서 Layer 4, Layer 5 동적 계층 분리 파싱
    layer4_content = ""
    layer5_content = ""
    if "[LAYER 5 - DYNAMIC_USER_TASK]:" in human_prompt:
        l4_part, l5_part = human_prompt.split("[LAYER 5 - DYNAMIC_USER_TASK]:", 1)
        layer4_content = l4_part.replace("[LAYER 4 - DYNAMIC_WORKING_CONTEXT]:", "").strip()
        layer5_content = l5_part.strip()
    else:
        layer4_content = "N/A"
        layer5_content = human_prompt
    
    # 3. 5계층이 위에서부터 순서대로 적층된 현대적 카드 데크 조립
    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 820px; border: 2px solid #334155; border-radius: 12px; overflow: hidden; background-color: #0B0F19; color: #E2E8F0; padding: 20px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);">
        <h3 style="margin-top: 0; color: #38BDF8; border-bottom: 2px solid #1E293B; padding-bottom: 12px; display: flex; align-items: center; gap: 8px;">
            <span>🛡️</span> Production Agent 5-Layer Prompt Stack
        </h3>
        
        <div style="font-size: 11px; color: #64748B; margin-bottom: 15px;">
            ※ 정적 시스템 프롬프트(L1~L3)는 파일로부터 비동기 로드되어 캐싱 영역에 고정되며, 동적 사용자 컨텍스트(L4~L5)만 런타임에 변환 교환됩니다.
        </div>

        <!-- [LAYER 1] GLOBAL BASE DIRECTIVE -->
        <div style="border: 1px solid #0284C7; border-radius: 8px; background-color: #0C1E32; padding: 12px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="background-color: #0284C7; color: #E0F2FE; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px;">LAYER 1: GLOBAL DIRECTIVE & PERSONALITY</span>
                <span style="color: #0EA5E9; font-size: 10px; font-weight: bold;">Cached Static Stack</span>
            </div>
            <pre style="white-space: pre-wrap; font-family: 'Consolas', 'Courier New', monospace; font-size: 10.5px; color: #93C5FD; margin: 0; max-height: 100px; overflow-y: auto; background: #070F1E; padding: 8px; border-radius: 4px; border: 1px solid #1E3A8A;">{layer1_text}</pre>
        </div>

        <!-- [LAYER 2] TOOL CAPABILITIES SPEC -->
        <div style="border: 1px solid #059669; border-radius: 8px; background-color: #062319; padding: 12px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="background-color: #059669; color: #D1FAE5; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px;">LAYER 2: TOOL CAPABILITIES & SPECIFICATION</span>
                <span style="color: #10B981; font-size: 10px; font-weight: bold;">Cached Static Stack</span>
            </div>
            <pre style="white-space: pre-wrap; font-family: 'Consolas', 'Courier New', monospace; font-size: 10.5px; color: #A7F3D0; margin: 0; max-height: 120px; overflow-y: auto; background: #02120C; padding: 8px; border-radius: 4px; border: 1px solid #064E3B;">{layer2_text}</pre>
        </div>

        <!-- [LAYER 3] PROJECT LAWS & POLICIES -->
        <div style="border: 1px solid #7C3AED; border-radius: 8px; background-color: #1B0F30; padding: 12px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="background-color: #7C3AED; color: #F5F3FF; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px;">LAYER 3: PROJECT LAWS & POLICIES (CLAUDE.md)</span>
                <span style="color: #A78BFA; font-size: 10px; font-weight: bold;">Cached Static Stack</span>
            </div>
            <pre style="white-space: pre-wrap; font-family: 'Consolas', 'Courier New', monospace; font-size: 10.5px; color: #DDD6FE; margin: 0; max-height: 100px; overflow-y: auto; background: #0E071A; padding: 8px; border-radius: 4px; border: 1px solid #4C1D95;">{layer3_text}</pre>
        </div>

        <!-- [DYNAMIC BOUNDARY MARKER] -->
        <div style="text-align: center; margin: 15px 0; border-top: 2px dashed #EF4444; border-bottom: 2px dashed #EF4444; padding: 6px 0; color: #FCA5A5; background-color: rgba(239, 68, 68, 0.08); font-weight: bold; font-size: 10.5px; letter-spacing: 1px; border-radius: 4px;">
            🛑 DYNAMIC_BOUNDARY (KV Cache Cut-off Line)
        </div>

        <!-- [LAYER 4] DYNAMIC WORKING CONTEXT -->
        <div style="border: 1px solid #EA580C; border-radius: 8px; background-color: #2D1405; padding: 12px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="background-color: #EA580C; color: #FFEDD5; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px;">LAYER 4: DYNAMIC WORKING CONTEXT</span>
                <span style="color: #F97316; font-size: 10px; font-weight: bold;">Uncached Dynamic Stack</span>
            </div>
            <pre style="white-space: pre-wrap; font-family: 'Consolas', 'Courier New', monospace; font-size: 10.5px; color: #FDBA74; margin: 0; background: #1B0B02; padding: 8px; border-radius: 4px; border: 1px solid #7C2D12;">{layer4_content}</pre>
        </div>

        <!-- [LAYER 5] DYNAMIC USER TASK -->
        <div style="border: 1px solid #EF4444; border-radius: 8px; background-color: #2D0F0F; padding: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="background-color: #EF4444; color: #FEE2E2; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px;">LAYER 5: DYNAMIC USER TASK / QUERY</span>
                <span style="color: #FCA5A5; font-size: 10px; font-weight: bold;">Uncached Dynamic Stack</span>
            </div>
            <pre style="white-space: pre-wrap; font-family: 'Consolas', 'Courier New', monospace; font-size: 10.5px; color: #FCA5A5; margin: 0; background: #1A0707; padding: 8px; border-radius: 4px; border: 1px solid #7F1D1D;">{layer5_content}</pre>
        </div>
    </div>
    """
    display(HTML(html_content))

