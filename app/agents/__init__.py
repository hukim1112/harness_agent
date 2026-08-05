from .utils import dynamic_response_format

# 🏭 에이전트 레지스트리 (Agent Registry)
# 새 에이전트 추가 시 여기에 정보 한 줄만 작성하면 서버, UI, CLI에 모두 반영됩니다.
AGENT_REGISTRY = [
    {
        "name": "chatbot",
        "module": "app.agents.chatbot",
        "prefix": "/chatbot",
        "tags": ["Chatbot"],
        "description": "도구 및 모니터링이 활성화된 기준완성형 챗봇 (서버/UI 테스트용)"
    },
    {
        "name": "harness_agent",
        "module": "app.agents.harness_agent",
        "prefix": "/harness_agent",
        "tags": ["HarnessAgent"],
        "description": "수강생들이 단계별 실무 미션을 통해 완성해나가는 실습용 에이전트"
    }
]

__all__ = [
    "AGENT_REGISTRY",
    "dynamic_response_format"
]
