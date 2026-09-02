from dataclasses import dataclass

@dataclass
class AgentContext:
    logging_enabled: bool = False
    log_path: str = "./artifacts/agent_audit_trail.json"
    response_mode: str = "chat"
    hitl_enabled: bool = False
    debug_mode: bool = False
    session_id: str = "unknown"
    
    # 🌟 메모리 연동 및 프롬프트 캐싱 가드레일용 환경 변수 선언
    user_permission: str = "GUEST"
    active_project: str = "UNKNOWN"
    recalled_memory: str = "No dynamic context provided."

    # 🧠 메모리 미들웨어 제어 플래그
    semantic_memory_enabled: bool = False
    episodic_memory_enabled: bool = False
    memory_learning_enabled: bool = False
    memory_dir: str = "./artifacts/memory"

