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
    ModelCallLimitMiddleware,
    SummarizationMiddleware
)
from langgraph.runtime import Runtime
from app.utils import get_llm
from langchain_core.prompts import ChatPromptTemplate

def clean_content(content) -> str:
    if isinstance(content, list):
        return "".join([block.get("text", "") if isinstance(block, dict) else str(block) for block in content])
    return str(content)

# 1. Summarization & Model call limit (Built-in)
summarize_middleware = SummarizationMiddleware
model_call_limit_middleware = ModelCallLimitMiddleware


# 2. Tool call limit (Custom @before_model)
@before_model(can_jump_to=["end"])
def tool_call_limit_middleware(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """도구 호출 횟수가 제한치(예: 3회)에 다다르면 강제로 제어권을 end 노드로 넘겨 탈출시키는 미들웨어"""
    messages = state.get("messages", [])
    # 궤적 이력 중 ToolMessage(도구 실행 결과)의 개수를 누적 카운트
    tool_calls_count = sum(1 for msg in messages if msg.__class__.__name__ == "ToolMessage")
    
    max_tool_limit = 3
    if tool_calls_count >= max_tool_limit:
        print(f"🛑 [Harness Middleware] Tool Call Limit Exceeded (Limit: {max_tool_limit}). Forcing termination.")
        # runtime API를 사용해 상태 그래프의 최종 end 노드로 강제 워프(Jump)
        runtime.jump_to("end")
    return None


# 3. Model fallback (Custom @wrap_model_call)
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


# 4. Model retry (Custom @wrap_model_call)
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


# 5. Auto Context Compactor (Custom @before_model)
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


# 6. Smart Context Indexer (Custom @before_model - Hybrid Line Indexing & Summarization)
@before_model
def smart_context_indexer(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """대용량 도구 출력이 감지되면 백그라운드 모델로 목차 생성(파일) 또는 압축 요약(기타 툴)을 수행하는 미들웨어"""
    import re
    messages = state.get("messages", [])
    modified = False
    new_messages = []
    
    # 15,000자 이상일 때 요약 인덱싱을 격발할 임계치 설정
    threshold = 15000
    
    for msg in messages:
        if msg.__class__.__name__ == "ToolMessage" and len(str(msg.content)) > threshold:
            original_content = str(msg.content)
            
            # 1. 파일 경로 추출 시도 (헤더 형식: [File: /abs/path ...])
            file_path_match = re.search(r"\[File:\s*([^\s\]]+)", original_content)
            
            # 2. 판정을 위한 백그라운드 LLM 기동
            try:
                llm = get_llm(model_name="gemini-3.5-flash", temperature=0.0)
                
                # A. 파일 읽기 도구 출력인 경우 ➔ 줄 번호 목차 인덱스 + 라인 힌트 생성
                if file_path_match:
                    detected_file_path = file_path_match.group(1)
                    print(f"🔍 [Harness Middleware] Large File Read detected ({len(original_content)} chars). Generating Line-hint Index...")
                    
                    system_prompt = (
                        "당신은 문서 분석 및 구조화 전문가입니다.\n"
                        "제시된 대용량 문서의 전체 흐름을 요약하되, 각 대주제/소주제별로 시작되는 대략적인 줄 번호(Line Number Range)를 매핑한 목차(TOC)를 생성해 주세요.\n\n"
                        "출력 형식 예시:\n"
                        "- Line 1~150: 인트로 및 전제 조건\n"
                        "- Line 151~420: 데이터베이스 연결 가이드 (포트, 유저 설정)\n"
                        "- Line 421~800: 트러블슈팅 및 예외 에러 코드 목록\n"
                    )
                    
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", system_prompt),
                        ("user", "다음 문서의 줄 번호 목차 인덱스를 생성하세요:\n\n{text}")
                    ])
                    
                    chain = prompt | llm
                    toc_index_raw = chain.invoke({"text": original_content[:60000]}).content
                    toc_index = clean_content(toc_index_raw).strip()
                    
                    compacted_content = (
                        f"[SYSTEM WARNING: 본문이 너무 길어 미들웨어에 의해 시맨틱 인덱싱 처리되었습니다. "
                        f"아래 목차를 참고하여 구체적인 정보 조회가 필요하다면 'file_read(file_path=\"{detected_file_path}\", offset=start_line, limit=limit)' 도구를 기동해 해당 영역을 상세히 읽어 질문에 답하세요.]\n\n"
                        f"{toc_index}"
                    )
                
                # B. 일반 검색/API 결과인 경우 ➔ 질문 맞춤형 압축 요약 수행
                else:
                    print(f"🔍 [Harness Middleware] Large Search Output detected ({len(original_content)} chars). Generating semantic summary...")
                    user_query = "사용자 질문"
                    if runtime and hasattr(runtime, "context"):
                        user_query = getattr(runtime.context, "user_query", "사용자 질문")
                    
                    system_prompt = (
                        f"당신은 정보 압축 전문가입니다. 사용자의 질문인 '{user_query}'에 답변하기 위해\n"
                        "아래 대용량 검색 본문에서 핵심적이고 직접적으로 연관된 정보만 추출하여 1,500자 내외로 압축 요약하세요."
                    )
                    
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", system_prompt),
                        ("user", "다음 텍스트에서 연관 정보를 압축 요약하세요:\n\n{text}")
                    ])
                    
                    chain = prompt | llm
                    summary_raw = chain.invoke({"text": original_content[:60000]}).content
                    summary = clean_content(summary_raw).strip()
                    
                    compacted_content = (
                        f"[SYSTEM WARNING: 검색 결과가 너무 길어 핵심 정보 위주로 압축 요약되었습니다.]\n\n"
                        f"{summary}"
                    )
                
                msg = ToolMessage(content=compacted_content, tool_call_id=msg.tool_call_id)
                modified = True
            except Exception as e:
                print(f"⚠️ [SmartContextIndexer] 요약/인덱싱 실패: {e}")
                compacted_content = (
                    f"[SYSTEM WARNING: 요약 실패로 강제 Truncate 되었습니다.]\n"
                    f"{original_content[:1000]}\n"
                    f"[... Truncated ...]\n"
                    f"{original_content[-1000:]}"
                )
                msg = ToolMessage(content=compacted_content, tool_call_id=msg.tool_call_id)
                modified = True
                
        new_messages.append(msg)
        
    if modified:
        return {"messages": new_messages}
    return None
