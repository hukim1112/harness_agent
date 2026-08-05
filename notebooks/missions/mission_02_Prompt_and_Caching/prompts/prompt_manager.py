import os
import json
from typing import List, Dict, Any

class PromptManager:
    def __init__(self, prompt_dir=None):
        if prompt_dir is None:
            # Default to the directory where this file resides
            prompt_dir = os.path.dirname(os.path.abspath(__file__))
        self.prompt_dir = prompt_dir
        self.boundary_marker = "=== DYNAMIC_BOUNDARY ==="
        
        # Load static layers from files
        self.l1_role = self._load_file("PROMPT.md", "You are Harness agent, a professional production-grade software engineering agent.")
        self.l3_rules = self._load_file("AGENT.md", "## Core Policy:\n1. Prioritize security boundaries.\n2. Do not mutate state without pre-approval.")
        
        # L2 and L4 are dynamic/set runtime
        self.l2_tools = "Available tools are registered dynamically at the runtime loop."
        self.l4_context = ""

    def _load_file(self, filename: str, fallback: str) -> str:
        filepath = os.path.join(self.prompt_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
        return fallback

    def set_reference_context(self, context_text: str):
        """Set the large L4 reference context for caching."""
        self.l4_context = context_text

    def build_tool_specifications(self, tools: List[Any]):
        """Dynamically build L2 tool specifications from LangChain tools list."""
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
        Assembles L1 ~ L4 into a single system prompt string.
        Optionally uses dynamic_state to interpolate runtime values.
        """
        permission_string = f"Current User Permissions: {dynamic_state.get('user_permission', 'NONE')}"
        project_string = f"Active Target Project: {dynamic_state.get('active_project', 'NONE')}"
        
        # Combine role, guidelines, tool specifications and project rules above cache boundary
        full_prompt = (
            f"=== ROLE (L1) ===\n{self.l1_role}\n\n"
            f"=== OPERATING GUIDELINES (L2) ===\n- {permission_string}\n- {project_string}\n\n"
            f"=== TOOLS SPECS (L2-SPEC) ===\n{self.l2_tools}\n\n"
            f"=== LOCAL PROJECT RULES (L3) ===\n{self.l3_rules}\n\n"
            f"{self.boundary_marker}\n\n"
            f"=== STATIC REFERENCE CONTEXT (L4) ===\n{self.l4_context}"
        )
        return full_prompt
