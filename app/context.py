"""
app/context.py — AgentContext (요청/세션 단위 런타임 실행 컨텍스트 DTO)
"""

from dataclasses import dataclass


@dataclass
class AgentContext:
    # ── 세션 / 사용자 / 워크스페이스 컨텍스트 ──
    agent_name: str = ""
    session_id: str = "unknown"
    parent_session_id: str = ""
    user_id: str = "default"
    workspace_dir: str = ""
    recalled_memory: str = ""

    # ── HITL 제어 ──
    hitl_enabled: bool = False

    # ── 계층형 메모리 미들웨어 제어 플래그 ──
    semantic_memory_enabled: bool = True
    semantic_learning_enabled: bool = True
    episodic_memory_enabled: bool = True
    episodic_learning_enabled: bool = True
