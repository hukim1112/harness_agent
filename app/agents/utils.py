from typing import Callable
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

@wrap_model_call
async def dynamic_response_format(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """런타임 컨텍스트에 따라 response_format 동적 선택 (chat 모드 지원)"""
    mode = "chat"
    if request.runtime.context and hasattr(request.runtime.context, "response_mode"):
        mode = request.runtime.context.response_mode
    
    if mode == "chat":
        request = request.override(response_format=None)
    
    return await handler(request)
