from dataclasses import dataclass

@dataclass
class AgentContext:
    logging_enabled: bool = False
    log_path: str = "./artifacts/agent_audit_trail.json"
    response_mode: str = "chat"
    hitl_enabled: bool = False
    debug_mode: bool = False
