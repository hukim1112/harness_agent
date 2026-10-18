from dataclasses import dataclass


@dataclass
class AgentContext:
    # ── 세션 / 사용자 / 워크스페이스 컨텍스트 ──
    agent_name: str = ""
    session_id: str = "unknown"
    parent_session_id: str = ""
    user_id: str = "default"
    workspace_dir: str = ""
    response_mode: str = "chat"
    debug_mode: bool = False

    # ── 로깅 및 HITL ──
    logging_enabled: bool = False
    log_path: str = "./artifacts/agent_audit_trail.json"
    hitl_enabled: bool = False

    # ── 메모리 연동 및 프롬프트 캐싱 가드레일용 환경 변수 ──
    user_permission: str = "GUEST"
    active_project: str = "UNKNOWN"
    recalled_memory: str = "No dynamic context provided."

    # ── 메모리 미들웨어 제어 플래그 ──
    semantic_memory_enabled: bool = True
    episodic_memory_enabled: bool = True
    memory_learning_enabled: bool = True
    semantic_learning_enabled: bool = True
    episodic_learning_enabled: bool = True
    memory_dir: str = "./artifacts/users/default/memory"
