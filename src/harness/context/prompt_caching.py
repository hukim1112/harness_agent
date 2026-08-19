"""
===============================================================================
[Harness Module 02-1] MultiLayeredPrompt & @dynamic_prompt Middleware
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: src/query.ts (Prompt Assembly & Boundaries)
- Slide Reference: Slide 10: 5-Layer Prompt Stack
- Architecture Notes: references/ref_02_context/architecture_notes.md
===============================================================================
"""

import os
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage


@dataclass
class RuntimeContext:
    user_id: str
    user_role: str        # "admin" / "viewer"
    deployment_env: str   # "production" / "staging"


@dataclass
class ModelRequest:
    runtime: RuntimeContext
    user_query: str


class MultiLayeredPrompt:
    def __init__(self, tools: list, custom_dynamic_l1: str = "", prompt_file_path="prompts/gpt_system_prompt.md", rules_file_path="prompts/AGENT.md"):
        self.prompt_file_path = prompt_file_path
        self.rules_file_path = rules_file_path
        self.boundary_marker = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"
        
        # 파일 경로로부터 각 계층 동적 로딩
        self.layer1_base = self._load_system_base_l1(custom_dynamic_l1)
        self.layer2_tools = self._build_tool_specifications(tools)
        self.layer5_rules = self._load_agent_rules()

    def _load_system_base_l1(self, custom_dynamic_l1: str) -> str:
        """기본 시스템 지침 파일(gpt_system_prompt.md)을 로드하고 동적 런타임 지침과 병합합니다."""
        possible_paths = [
            self.prompt_file_path,
            os.path.join("prompts", os.path.basename(self.prompt_file_path)),
            os.path.join("notebooks", self.prompt_file_path),
            os.path.join("notebooks", "prompts", os.path.basename(self.prompt_file_path)),
            os.path.join("..", self.prompt_file_path)
        ]
        
        content = ""
        for p in possible_paths:
            if os.path.exists(p) and os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                break
                
        if not content:
            # 폴백용 표준 시스템 프로필
            content = "You are a helpful production agent trained to operate safely."
            
        base_tmpl = content.replace("# [STATIC SYSTEM PROMPT: GPT-4o Production Agent Spec]", "").strip()
        
        # 런타임 미들웨어 지침이 존재할 경우 표준 지침 위에 결합
        if custom_dynamic_l1:
            return f"🎯 [RUN-TIME CONTEXTUAL DIRECTIVE]\n{custom_dynamic_l1}\n\n📋 [STANDARD SYSTEM DIRECTIVE]\n{base_tmpl}"
        return base_tmpl

    def _build_tool_specifications(self, tools: list) -> str:
        """바인딩된 도구들의 스키마(API 규격)를 기계적 명세 텍스트로 동적 조립합니다."""
        spec_lines = []
        for idx, t in enumerate(tools):
            spec_lines.append(f"### [Tool {idx+1}] name: {t.name}")
            spec_lines.append(f"  - description: {t.description}")
            if hasattr(t, "args"):
                spec_lines.append(f"  - arguments_schema: {json.dumps(t.args, ensure_ascii=False)}")
            spec_lines.append("")
        return "\n".join(spec_lines).strip()

    def _load_agent_rules(self) -> str:
        """AGENT.md 파일로부터 Layer 5 프로젝트 규칙을 동적 로드합니다."""
        possible_paths = [
            self.rules_file_path,
            os.path.join("prompts", os.path.basename(self.rules_file_path)),
            os.path.join("notebooks", self.rules_file_path),
            os.path.join("notebooks", "prompts", os.path.basename(self.rules_file_path)),
            os.path.join("..", self.rules_file_path)
        ]
        
        content = ""
        for p in possible_paths:
            if os.path.exists(p) and os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                break
                
        if not content:
            # 폴백용 기본 보안 룰
            content = "## Core Policy:\n1. Prioritize security boundaries.\n2. Do not mutate state without pre-approval."
            
        return content

    def assemble_layered_system_prompt(self, dynamic_context: str) -> str:
        """정적 계층(L1~L2)과 동적 환경 계층(L3~L5)을 결합하여 에이전트용 최종 시스템 프롬프트 문자열을 반환합니다.
        (Layer 5인 사용자 최종 입력은 메시지 리스트의 HumanMessage를 통해 자연스럽게 흐릅니다.)
        """
        system_prompt = (
            f"[LAYER 1: GLOBAL BASE & PERSONALITY]\n{self.layer1_base}\n\n"
            f"[LAYER 2: TOOL SPECIFICATIONS]\n{self.layer2_tools}\n\n"
            f"{self.boundary_marker}\n\n"
            f"[LAYER 3/4 - DYNAMIC_WORKING_CONTEXT]:\n{dynamic_context}\n\n"
            f"[LAYER 5 - LOCAL PROJECT RULES]:\n{self.layer5_rules}"
        )
        return system_prompt

    def validate_dynamic_boundary_guardrail(self, system_prompt: str) -> dict:
        """경계선 오염 여부 및 캐싱 안전성 검증 가드레일"""
        marker = self.boundary_marker if self.boundary_marker in system_prompt else "=== DYNAMIC_BOUNDARY ==="
        if marker not in system_prompt:
            return {"guardrail_status": "FAILED_BOUNDARY_MISSING", "is_cache_safe": False}
            
        static_part, _ = system_prompt.split(marker, 1)
        is_safe = "TOOL SPECIFICATIONS" in static_part or "GLOBAL BASE" in static_part
        return {
            "guardrail_status": "PASSED" if is_safe else "FAILED_STATIC_MUTATED",
            "is_cache_safe": is_safe
        }


def dynamic_prompt(func):
    """데코레이팅된 함수의 리턴값(동적 지침)을 가져와 
    MultiLayeredPrompt 5계층 스택의 L1 최상단에 자동으로 결합해 주는 데코레이터 미들웨어입니다.
    """
    def wrapper(request: ModelRequest, tools: list = [], *args, **kwargs):
        # 1. 데코레이팅된 함수를 호출하여 동적 L1 시스템 지침 생성
        dynamic_base_system_prompt = func(request, *args, **kwargs)
        
        # 2. MultiLayeredPrompt 기동 (경로 유연성 기본값 적용)
        prompt_builder = MultiLayeredPrompt(
            tools=tools,
            custom_dynamic_l1=dynamic_base_system_prompt
        )
        
        # 3. L4 및 L5 결합
        dynamic_trajectory = f"User Role: {request.runtime.user_role} | Environment: {request.runtime.deployment_env}"
        messages = prompt_builder.assemble_5layer_prompt(
            dynamic_context=dynamic_trajectory,
            user_task=request.user_query
        )
        
        return messages
    return wrapper
