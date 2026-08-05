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
        
        # Skills context (Loaded from Skills.md)
        self.skills_context = self._load_file("Skills.md", "No public skills registered.")
        
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
            f"=== PUBLIC SKILLS CATALOG ===\n{self.skills_context}\n\n"
            f"=== TOOLS SPECS (L3) ===\n{self.l3_tools}\n\n"
            f"=== STATIC REFERENCE CONTEXT ===\n{self.static_reference}\n\n"
            f"{self.boundary_marker}\n\n"
            f"=== DYNAMIC RULES/ENV (L4) ===\n{l4_env}\n\n"
            f"=== DYNAMIC CONTEXT (L5) ===\n{self.l5_dynamic_context}"
        )
        return full_prompt


# 1. 원본 동적 프롬프트 조립 함수 (데코레이터가 없어 노트북에서 직접 호출하여 테스트 가능)
def build_harness_agent_prompt(request: ModelRequest) -> str:
    ctx = request.runtime.context
    
    # runtime.context로부터 권한/환경 정보 획득 (L4)
    user_permission = getattr(ctx, "user_permission", "GUEST")
    active_project = getattr(ctx, "active_project", "UNKNOWN")
    
    dynamic_state = {
        "user_permission": user_permission,
        "active_project": active_project
    }
    
    # 파일들(PROMPT.md, AGENT.md)을 읽어오는 PromptManager 인스턴스화
    prompt_dir = os.path.dirname(os.path.abspath(__file__))
    pm = PromptManager(prompt_dir=prompt_dir)
    
    # 도구 규격 동적 반영 (L3)
    if hasattr(request, "tools") and request.tools:
        pm.build_tool_specifications(request.tools)
        
    # 정적/동적 참고자료나 메모리 바인딩 (L5)
    recalled_memory = getattr(ctx, "recalled_memory", None)
    if not recalled_memory or recalled_memory == "No dynamic context provided.":
        try:
            # SQLite 기반 장기 기억 매니저 로드 및 자동 검색
            from harness.context.hermes_memory import HermesMemoryManager
            db_path = "hermes_memory_production.db"
            if os.path.exists(db_path):
                memory_mgr = HermesMemoryManager(db_path=db_path)
                user_query = ""
                if hasattr(request, "messages") and request.messages:
                    user_query = request.messages[-1].content
                elif hasattr(request, "user_query") and request.user_query:
                    user_query = request.user_query
                
                if user_query:
                    # 질문 기반 연관 대화 에피소드(L2) 및 규칙 복원
                    recalled_eps = memory_mgr.recall_episodic(user_query)
                    if recalled_eps:
                        recalled_memory = "\n".join([f"- [{ep[0].upper()}]: {ep[1]}" for ep in recalled_eps])
        except Exception:
            pass
            
    if not recalled_memory:
        recalled_memory = "No dynamic context provided."
        
    pm.set_dynamic_context(recalled_memory)
    
    return pm.build_system_prompt(dynamic_state)


# 2. 원본 동적 프롬프트 조립 함수 (데코레이터가 없어 노트북에서 직접 호출하여 테스트 가능)
build_harness_agent_prompt_fn = build_harness_agent_prompt

