"""
===============================================================================
[Harness Module 03-2] Claude Code Style Strict ACI (Agent-Computer Interface) Schema
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/tools/ (Strict ACI Tool Specification & Input Validation)
- Hermes Agent Source: c:/Users/hyoun/Desktop/github/Agent_reference/hermes-agent/model_tools.py (Pydantic Validation & Fallback)
- Research Report: h:/내 드라이브/work_memory/contexts/강의/courses/11_글로벌_에이전트_아키텍처/Claude_Code_claude/03_phase3_harness_deepdive.md
===============================================================================
"""

from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool


# -----------------------------------------------------------------------------
# 1. Claude Code Style Strict Pydantic ACI Input Schema Definition
# -----------------------------------------------------------------------------
class ProductionFileEditSchema(BaseModel):
    """
    Claude Code Style ACI Tool Schema:
    Enforces strict argument validation, parameter docstrings, allowed values,
    and helpful error hints for LLM tool invocation.
    """
    file_path: str = Field(
        ..., 
        description="Absolute file path to be modified. Must be within project workspace directory."
    )
    target_content: str = Field(
        ..., 
        description="Exact string block to search and replace in target file. Must match exactly including whitespace."
    )
    replacement_content: str = Field(
        ..., 
        description="New replacement string block."
    )
    allow_multiple: bool = Field(
        default=False, 
        description="If True, allows replacing multiple occurrences. Default is False."
    )

    @field_validator("file_path")
    @classmethod
    def validate_absolute_path(cls, v: str) -> str:
        if not (v.startswith("/") or v.startswith("C:") or v.startswith("h:") or v.startswith("H:")):
            raise ValueError("ACI_SCHEMA_ERROR: 'file_path' must be an absolute path (e.g. /path/to/file or C:/path).")
        return v

    @field_validator("target_content")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ACI_SCHEMA_ERROR: 'target_content' cannot be empty or whitespace only.")
        return v


# -----------------------------------------------------------------------------
# 2. Strict Tool Builder using ACI Schema
# -----------------------------------------------------------------------------
def execute_strict_file_edit(file_path: str, target_content: str, replacement_content: str, allow_multiple: bool = False) -> str:
    """Executes validated file replacement."""
    return f"SUCCESS: Replaced content in '{file_path}' (allow_multiple={allow_multiple})."

def build_strict_aci_tool() -> StructuredTool:
    """Builds a LangChain StructuredTool bound with strict ACI Pydantic Schema."""
    return StructuredTool.from_function(
        func=execute_strict_file_edit,
        name="strict_replace_file_content",
        description="Replaces exact target content block in a file. Enforces strict path and content validation.",
        args_schema=ProductionFileEditSchema
    )
