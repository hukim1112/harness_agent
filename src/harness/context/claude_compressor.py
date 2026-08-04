"""
===============================================================================
[Harness Module 02-3] Claude Code 4-Stage Context Compaction Engine
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- Claude Code Source: c:/Users/hyoun/Desktop/github/Agent_reference/superview.sh-claude-code/src/compact/
- Slide Reference: h:/내 드라이브/work_memory/contexts/강의/slides/11_글로벌_에이전트_아키텍처/v1.1/02_claude_code.html (Slide 17-20: Compaction Engines)
- Architecture Notes: h:/내 드라이브/work_memory/contexts/강의/handson/10_하네스_프로덕션_에이전트/references/ref_02_context/architecture_notes.md
===============================================================================
"""

import json
import logging
from typing import List, Dict, Any, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from utils.llm import get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClaudeCompactor")


class CompactedTrajectorySchema(BaseModel):
    summary_of_past_turns: str = Field(description="High-level summary of accomplished milestones and user goal.")
    key_anchor_facts: List[str] = Field(description="Crucial facts (file paths, decisions, error states) that must be preserved.")


class ClaudeContextCompactor:
    """
    Implements 4 Compaction Techniques from Claude Code Harness Architecture:
    1. Micro-compaction: Prunes verbose tool inputs/outputs inline.
    2. Auto-compaction: Triggers when token usage exceeds threshold (e.g. 80%), creating structured summary.
    3. Reactive Compaction: Emergency pruning triggered by 413 prompt_too_long API error.
    4. Context Drain: Truncates low-priority older messages from sliding window.
    """
    def __init__(self, token_threshold: int = 10000):
        self.token_threshold = token_threshold

    # -------------------------------------------------------------------------
    # 1. Micro-compaction (Inline Pruning of Tool Outputs)
    # -------------------------------------------------------------------------
    def apply_micro_compaction(self, messages: List[Any]) -> List[Any]:
        """Micro-compaction: Replaces long tool outputs (>500 chars) with concise summaries."""
        compacted = []
        for msg in messages:
            if isinstance(msg, ToolMessage) and len(str(msg.content)) > 500:
                short_content = f"[MICRO_COMPACTED TOOL OUTPUT]: {str(msg.content)[:200]}... (Truncated {len(str(msg.content))-200} bytes)"
                compacted.append(ToolMessage(content=short_content, tool_call_id=msg.tool_call_id))
            else:
                compacted.append(msg)
        return compacted

    # -------------------------------------------------------------------------
    # 2. Auto-compaction (Threshold-driven Structured Summary)
    # -------------------------------------------------------------------------
    def apply_auto_compaction(self, messages: List[Any], model_name: str = "gemini-2.5-pro") -> Tuple[List[Any], Dict[str, Any]]:
        """Auto-compaction: Summarizes full conversation history into Anchor Memories when threshold exceeded."""
        total_tokens_est = sum(len(str(m.content).split()) for m in messages)
        
        if total_tokens_est < self.token_threshold and len(messages) < 10:
            return messages, {"compacted": False, "reason": "Under threshold"}

        logger.info(f"Auto-compaction triggered! Estimated tokens: {total_tokens_est}")
        
        try:
            llm = get_llm(model_name=model_name, temperature=0.0).with_structured_output(CompactedTrajectorySchema)
            prompt = f"Summarize past conversation trajectory into key anchors:\n{[str(m.content) for m in messages]}"
            summary_res = llm.invoke(prompt)
            
            compacted_system = SystemMessage(content=(
                f"[AUTO_COMPACTED_ANCHOR_MEMORY]\n"
                f"Summary: {summary_res.summary_of_past_turns}\n"
                f"Key Anchor Facts: {json.dumps(summary_res.key_anchor_facts, ensure_ascii=False)}"
            ))
            
            # Keep system prompt + compacted anchor + last 2 recent turns
            new_messages = [messages[0], compacted_system] + messages[-2:]
            return new_messages, {"compacted": True, "reduction_ratio": round(len(new_messages)/len(messages), 2)}
            
        except Exception as e:
            # Fallback Auto-compaction
            compacted_system = SystemMessage(content=f"[AUTO_COMPACTED_FALLBACK]: Pruned older turns. Preserved active user request.")
            new_messages = [messages[0], compacted_system, messages[-1]]
            return new_messages, {"compacted": True, "fallback": str(e)}

    # -------------------------------------------------------------------------
    # 3. Reactive Compaction (Emergency 413 Handler)
    # -------------------------------------------------------------------------
    def apply_reactive_compaction(self, messages: List[Any]) -> List[Any]:
        """Reactive Compaction: Emergency aggressive pruning on 413 payload error."""
        logger.warning("Reactive Compaction activated! Performing emergency trajectory drain.")
        # Keep System Prompt (Index 0) and Last Human Message (Index -1)
        system_msg = messages[0]
        last_msg = messages[-1]
        
        emergency_notice = SystemMessage(content="[REACTIVE_COMPACTION_DRAIN]: Emergency pruning applied due to 413 payload error. Older history cleared.")
        return [system_msg, emergency_notice, last_msg]

    # -------------------------------------------------------------------------
    # 4. Context Drain / Truncation (Sliding Window Drain)
    # -------------------------------------------------------------------------
    def apply_context_drain(self, messages: List[Any], keep_last_n: int = 6) -> List[Any]:
        """Context Drain: Truncates older messages using a sliding window."""
        if len(messages) <= keep_last_n + 1:
            return messages
            
        system_msg = messages[0]
        recent_messages = messages[-keep_last_n:]
        drain_notice = SystemMessage(content=f"[CONTEXT_DRAINED]: Drained {len(messages) - keep_last_n - 1} older turns.")
        
        return [system_msg, drain_notice] + recent_messages
