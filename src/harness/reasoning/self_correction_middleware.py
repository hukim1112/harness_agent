"""
===============================================================================
[Harness Module] Self-Correction Middlewares (Built-in & Custom Hybrid Suite)
===============================================================================
Reference:
- Summarization: SummarizationMiddleware (Built-in)
- Model call limit: ModelCallLimitMiddleware (Built-in)
- Tool call limit: Custom tool_call_limit (Custom @before_model)
- Model fallback: Custom dynamic_model_fallback (Custom @wrap_model_call)
- Model retry: Custom retry_on_transient_error (Custom @wrap_model_call)
===============================================================================
"""
import os
import time
from typing import Callable, Any
from langchain_core.messages import ToolMessage
from langchain.agents.middleware import (
    AgentMiddleware, 
    AgentState, 
    ModelRequest, 
    ModelResponse,
    before_model, 
    wrap_model_call,
    ModelCallLimitMiddleware,  # Built-in: Model call limit
    SummarizationMiddleware    # Built-in: Summarization
)
from langgraph.runtime import Runtime
from utils.llm import get_llm

# =============================================================================
# 1. Summarization (Built-in) -> 별칭 제공
# =============================================================================
# 사용자가 직관적으로 호출할 수 있도록 랩핑하거나 별칭 제공
summarize_middleware = SummarizationMiddleware


# =============================================================================
# 2. Model call limit (Built-in) -> 별칭 제공
# =============================================================================
model_call_limit_middleware = ModelCallLimitMiddleware


# =============================================================================
# 3. Tool call limit (Custom @before_model)
# =============================================================================
@before_model(can_jump_to=["end"])
def tool_call_limit_middleware(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """도구 호출 횟수가 제한치(예: 3회)에 다다르면 강제로 제어권을 end 노드로 넘겨 탈출시키는 미들웨어"""
    messages = state.get("messages", [])
    # 궤적 이력 중 ToolMessage(도구 실행 결과)의 개수를 누적 카운트
    tool_calls_count = sum(1 for msg in messages if msg.__class__.__name__ == "ToolMessage")
    
    # 예제 테스트를 위해 제한치를 3회로 설정
    max_tool_limit = 3
    if tool_calls_count >= max_tool_limit:
        print(f"🛑 [Harness Middleware] Tool Call Limit Exceeded (Limit: {max_tool_limit}). Forcing termination.")
        # runtime API를 사용해 상태 그래프의 최종 end 노드로 강제 워프(Jump)
        runtime.jump_to("end")
    return None


# =============================================================================
# 4. Model fallback (Custom @wrap_model_call)
# =============================================================================
@wrap_model_call
def dynamic_model_fallback(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """메인 모델 API 호출 실패 시 백업 모델(gemini-2.5-pro)로 강제 스위칭하는 미들웨어"""
    try:
        return handler(request)
    except Exception as error:
        print(f"🔄 [Harness Middleware] Main Model Call Failed ({error}). Activating Fallback backup model...")
        # 백업용 안전 모델 로드
        backup_llm = get_llm(model_name="gemini-2.5-pro", temperature=0.0)
        # 통신 요청의 타겟 모델을 백업 모델로 대체하여 재호출
        request.model = backup_llm
        return handler(request)


# =============================================================================
# 5. Model retry (Custom @wrap_model_call)
# =============================================================================
@wrap_model_call
def retry_on_transient_error(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """API 호출 에러 발생 시 최대 3회 지수 백오프로 자동 복구하는 미들웨어"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return handler(request)
        except Exception as error:
            if attempt == max_retries - 1:
                raise error
            sleep_time = 2 ** attempt
            print(f"⚠️ [Harness Middleware] Model Call Failed. Retrying ({attempt+1}/{max_retries}) in {sleep_time}s...")
            time.sleep(sleep_time)


# =============================================================================
# 6. Auto Context Compactor (Custom @before_model)
# =============================================================================
@before_model
def auto_context_compactor(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """413 Payload Too Large 방지를 위해 너무 큰 툴 출력(ToolMessage)을 가로채 앞뒤만 남기고 요약(Snip)하는 미들웨어"""
    messages = state.get("messages", [])
    modified = False
    new_messages = []
    
    for msg in messages:
        if msg.__class__.__name__ == "ToolMessage" and len(str(msg.content)) > 300:
            original_len = len(str(msg.content))
            compacted_content = (
                f"{str(msg.content)[:100]}\n"
                f"[... SYSTEM NOTE: Truncated by auto_context_compactor middleware (original length: {original_len} chars) ...]\n"
                f"{str(msg.content)[-100:]}"
            )
            msg = ToolMessage(content=compacted_content, tool_call_id=msg.tool_call_id)
            modified = True
        new_messages.append(msg)
        
    if modified:
        print("✂️ [Harness Middleware] Oversized Tool Message detected. Context Compaction applied!")
        return {"messages": new_messages}
        
    return None
