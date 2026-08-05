import os
import json
from typing import List, Dict, Any

# 🌟 LangChain 미들웨어 스펙을 위한 클래스 및 데코레이터 임포트
from langchain.agents.middleware import dynamic_prompt, ModelRequest

class PromptManager:
    def __init__(self, prompt_dir=None):
        if prompt_dir is None:
            prompt_dir = os.path.dirname(os.path.abspath(__file__))
        self.prompt_dir = prompt_dir
        self.boundary_marker = "=== DYNAMIC_BOUNDARY ==="
        
        # L1: ROLE (Static, loaded from PROMPT.md)
        self.l1_role = self._load_file("PROMPT.md", "You are the Harness Agent, a professional production-grade software engineering agent.")
        
        # L2: GUIDE (Static, loaded from AGENT.md)
        self.l2_guidelines = self._load_file("AGENT.md", "## Core Policy:\n1. Prioritize security boundaries.\n2. Do not mutate state without pre-approval.")
        
        # L3: Tools (Static specs, built dynamically)
        self.l3_tools = "Available tools are registered dynamically at the runtime loop."
        
        # Static Reference Context (Stored above boundary to enable caching benchmark)
        self.static_reference = ""
        
        # L5: Dynamic Context (Dynamic info, e.g. memories, status, etc.)
        self.l5_dynamic_context = "No dynamic context provided."

    def _load_file(self, filename: str, fallback: str) -> str:
        filepath = os.path.join(self.prompt_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
        return fallback

    def set_reference_context(self, context_text: str):
        """Sets the large static reference manual (caching benchmark target) above the boundary."""
        self.static_reference = context_text

    def set_dynamic_context(self, context_text: str):
        """Sets the dynamic context (L5) below the boundary."""
        self.l5_dynamic_context = context_text

    def build_tool_specifications(self, tools: List[Any]):
        """Dynamically build L3 tool specifications from LangChain tools list."""
        spec_lines = []
        for idx, t in enumerate(tools):
            spec_lines.append(f"### [Tool {idx+1}] name: {t.name}")
            spec_lines.append(f"  - description: {t.description}")
            if hasattr(t, "args"):
                spec_lines.append(f"  - arguments_schema: {json.dumps(t.args, ensure_ascii=False)}")
            spec_lines.append("")
        self.l3_tools = "\n".join(spec_lines).strip()

    def build_system_prompt(self, dynamic_state: dict) -> str:
        """
        Assembles 5-layer prompt stack with the boundary marker at the correct position.
        L1, L2, L3, and Static Reference are placed ABOVE the boundary marker (cached).
        L4 (Dynamic environment rules) and L5 (Dynamic Context) are placed BELOW (uncached).
        """
        # L4: Dynamic Project Rules & Environment
        permission_string = f"Current User Permissions: {dynamic_state.get('user_permission', 'NONE')}"
        project_string = f"Active Target Project: {dynamic_state.get('active_project', 'NONE')}"
        l4_env = f"- {permission_string}\n- {project_string}"
        
        full_prompt = (
            f"=== ROLE (L1) ===\n{self.l1_role}\n\n"
            f"=== OPERATING GUIDELINES (L2) ===\n{self.l2_guidelines}\n\n"
            f"=== TOOLS SPECS (L3) ===\n{self.l3_tools}\n\n"
            f"=== STATIC REFERENCE CONTEXT ===\n{self.static_reference}\n\n"
            f"{self.boundary_marker}\n\n"
            f"=== DYNAMIC RULES/ENV (L4) ===\n{l4_env}\n\n"
            f"=== DYNAMIC CONTEXT (L5) ===\n{self.l5_dynamic_context}"
        )
        return full_prompt


# 🌟 @dynamic_prompt 데코레이터가 적용된 프로덕션 규격 미들웨어 정의
@dynamic_prompt
def harness_agent_prompt_middleware(request: ModelRequest) -> str:
    """
    Harness Agent를 위한 dynamic_prompt 미들웨어.
    에이전트 실행 직전에 호출되어, runtime.context 및 request.tools를
    결합한 최종 5계층 시스템 프롬프트를 빌드하여 반환합니다.
    """
    ctx = request.runtime.context
    
    # 1. runtime.context로부터 권한/환경 정보 획득 (L4)
    user_permission = getattr(ctx, "user_permission", "GUEST")
    active_project = getattr(ctx, "active_project", "UNKNOWN")
    
    dynamic_state = {
        "user_permission": user_permission,
        "active_project": active_project
    }
    
    # 2. 파일들(PROMPT.md, AGENT.md)을 읽어오는 PromptManager 인스턴스화
    # (__file__ 기준으로 정확하게 prompts 디렉토리를 바인딩합니다)
    prompt_dir = os.path.dirname(os.path.abspath(__file__))
    pm = PromptManager(prompt_dir=prompt_dir)
    
    # 3. 도구 규격 동적 반영 (L3)
    if hasattr(request, "tools") and request.tools:
        pm.build_tool_specifications(request.tools)
        
    # 4. 정적/동적 참고자료나 메모리 바인딩 (L5)
    # (추후 SQLite 에피소드 메모리 복원 시 여기에 텍스트를 주입합니다)
    recalled_memory = getattr(ctx, "recalled_memory", "No dynamic context provided.")
    pm.set_dynamic_context(recalled_memory)
    
    # 5. 완성된 시스템 프롬프트 조립 및 반환
    return pm.build_system_prompt(dynamic_state)
