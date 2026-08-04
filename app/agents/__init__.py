from .utils import dynamic_response_format

# 🏭 에이전트 레지스트리 (Agent Registry)
# 새 에이전트 추가 시 여기에 정보 한 줄만 작성하면 서버, UI, CLI에 모두 반영됩니다.
AGENT_REGISTRY = [
    {
        "name": "chatbot",
        "module": "app.agents.chatbot",
        "prefix": "/chatbot",
        "tags": ["Chatbot"],
        "description": "도구 없이 자연어 대화만 수행하는 범용 AI 어시스턴트"
    }
]

__all__ = [
    "AGENT_REGISTRY",
    "dynamic_response_format"
]
