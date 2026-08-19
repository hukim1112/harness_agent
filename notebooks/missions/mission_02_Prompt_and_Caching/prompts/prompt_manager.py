import os
import json
from typing import List, Dict, Any

# 🌟 LangChain 미들웨어 스펙을 위한 클래스 및 데코레이터 임포트
from langchain.agents.middleware import dynamic_prompt, ModelRequest
from harness.context.skill_builder import SkillPromptBuilder

class PromptManager:
    def __init__(self, prompt_dir=None):
        if prompt_dir is None:
            prompt_dir = os.path.dirname(os.path.abspath(__file__))
        self.prompt_dir = prompt_dir
        self.boundary_marker = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"
        
        # Layer 1: System Identity & Core Role (Static, loaded from PROMPT.md)
        self.l1_role = self._load_file("PROMPT.md", "You are the Harness Agent, a professional production-grade software engineering agent.")
        
        # Layer 2: Tools (Static specs, built dynamically)
        self.l2_tools = "Available tools are registered dynamically at the runtime loop."
        
        # Skills context (Layer 2: Dynamically scanned and assembled via SkillPromptBuilder)
        skills_guide_file = os.path.join(self.prompt_dir, "Skills.md")
        if not os.path.exists(skills_guide_file):
            skills_guide_file = os.path.join(self.prompt_dir, "SKILL.md")
        self.skill_builder = SkillPromptBuilder(
            skills_dirs=["./skills", "./.agents/skills", "skills"],
            guidelines_path=skills_guide_file
        )
        self.skills_context = self.skill_builder.assemble()
        
        # Static Reference Context (Stored above boundary to enable caching benchmark)
        self.static_reference = ""
        
        # Layer 4: Recalled Memory & Dynamic Context (Below boundary)
        self.l4_dynamic_context = "No dynamic context provided."
        
        # Layer 5: Project & User Rules (AGENT.md, below boundary)
        self.l5_agent_rules = self._load_file("AGENT.md", "## Core Policy:\n1. Prioritize security boundaries.\n2. Do not mutate state without pre-approval.")

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
        """Sets the dynamic context (L4) below the boundary."""
        self.l4_dynamic_context = context_text

    def build_tool_specifications(self, tools: List[Any]):
        """Dynamically build Layer 2 tool specifications from LangChain tools list."""
        spec_lines = []
        for idx, t in enumerate(tools):
            spec_lines.append(f"### [Tool {idx+1}] name: {t.name}")
            spec_lines.append(f"  - description: {t.description}")
            if hasattr(t, "args"):
                spec_lines.append(f"  - arguments_schema: {json.dumps(t.args, ensure_ascii=False)}")
            spec_lines.append("")
        self.l2_tools = "\n".join(spec_lines).strip()

    def build_system_prompt(self, dynamic_state: dict) -> str:
        """
        Assembles standard 5-layer prompt stack with the boundary marker at the correct position.
        Layer 1~2 & Static Reference are placed ABOVE the boundary marker (cached).
        Layer 3~5 (Dynamic Environment, Memory Context, AGENT.md) are placed BELOW (uncached).
        """
        # Layer 3: Dynamic Environment (Permission, Project, CWD)
        permission_string = f"Current User Permissions: {dynamic_state.get('user_permission', 'NONE')}"
        project_string = f"Active Target Project: {dynamic_state.get('active_project', 'NONE')}"
        cwd_string = f"CWD: {dynamic_state.get('cwd', '/workspace')}"
        l3_env = f"- {permission_string}\n- {project_string}\n- {cwd_string}"
        
        self.skills_context = self.skill_builder.assemble()
        
        static_part = (
            f"=== Layer 1: System Identity & Core Role ===\n{self.l1_role}\n\n"
            f"=== Layer 2: Tool Capabilities & Available Skills ===\n{self.l2_tools}\n\n"
            f"=== Available Skills Catalog ===\n{self.skills_context}\n\n"
            f"=== Static Reference Context ===\n{self.static_reference}\n\n"
            f"{self.boundary_marker}"
        )
        
        dynamic_part = (
            f"=== Layer 3: Dynamic Session Environment ===\n{l3_env}\n\n"
            f"=== Layer 4: Recalled Memory & Dynamic Context ===\n{self.l4_dynamic_context}\n\n"
            f"=== Layer 5: User & Project Rules (AGENT.md) ===\n{self.l5_agent_rules}"
        )
        
        return f"{static_part}\n\n{dynamic_part}"


# 1. 원본 동적 프롬프트 조립 함수 (데코레이터가 없어 노트북에서 직접 호출하여 테스트 가능)
def build_harness_agent_prompt(request: ModelRequest) -> str:
    ctx = request.runtime.context
    
    # 1. Layer 3: 권한/환경 정보 획득
    user_permission = getattr(ctx, "user_permission", "GUEST")
    active_project = getattr(ctx, "active_project", "UNKNOWN")
    
    dynamic_state = {
        "user_permission": user_permission,
        "active_project": active_project
    }
    
    # 파일들(PROMPT.md, AGENT.md)을 읽어오는 PromptManager 인스턴스화
    prompt_dir = os.path.dirname(os.path.abspath(__file__))
    pm = PromptManager(prompt_dir=prompt_dir)
    
    # 2. Layer 2: 도구 규격 동적 반영
    if hasattr(request, "tools") and request.tools:
        pm.build_tool_specifications(request.tools)
        
    # 3. Layer 4: SQLite 기반 장기 기억(L2 에피소드) 인출
    recalled_memory = getattr(ctx, "recalled_memory", None)
    if not recalled_memory or recalled_memory == "No dynamic context provided.":
        try:
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
                    recalled_eps = memory_mgr.recall_episodic(user_query)
                    if recalled_eps:
                        recalled_memory = "\n".join([f"- [{ep[0].upper()}]: {ep[1]}" for ep in recalled_eps])
        except Exception:
            pass
            
    if not recalled_memory:
        recalled_memory = "No dynamic context provided."
        
    pm.set_dynamic_context(recalled_memory)
    
    return pm.build_system_prompt(dynamic_state)


# 2. 🌟 @dynamic_prompt 데코레이터가 적용된 프로덕션 규격 미들웨어 객체
harness_agent_prompt_middleware = dynamic_prompt(build_harness_agent_prompt)
