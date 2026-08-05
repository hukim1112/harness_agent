import os
import json
from langchain.agents.middleware import AgentMiddleware, before_model, wrap_model_call, ModelResponse
from langchain_core.messages import AIMessage
from app.utils import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.utils.message_utils import normalize_content

class InputSafetyGuardrail(AgentMiddleware):
    """입력 유해 규정 검사 보안 필터 미들웨어 (Llama Guard 아키텍처 계승)"""
    def __init__(self, model="gemini-3.5-flash", temperature=0.0):
        self.llm = get_llm(model_name=model, temperature=temperature)
        
    def wrap_model_call(self, request, handler):
        messages = []
        if isinstance(request, dict):
            messages = request.get("messages", [])
        elif hasattr(request, "input_data") and request.input_data:
            messages = request.input_data.get("messages", [])
        elif hasattr(request, "messages") and request.messages:
            messages = request.messages
            
        if not messages:
            return handler(request)
            
        user_query = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
        user_query = normalize_content(user_query)
        
        # 유해 규정 심사 가이드라인 정의
        system_prompt = """
        당신은 에이전트의 입력/출력 텍스트를 검열하는 보안 필터입니다.
        제시된 텍스트가 아래 3가지 유해 카테고리에 해당하는지 엄격하게 심사하세요.
        
        카테고리 리스트:
        - S1: 무기 제조, 테러 및 폭력적 범죄 모의
        - S2: 크레덴셜 해킹 및 사이버 네트워크 공격 시도
        - S3: 마약, 성적 유해물 및 자해 행위 묘사
        
        응답 형식 규격:
        - 유해 규정을 위반한 경우: 오직 'unsafe [카테고리코드]' 형태로만 답변하세요. (예: unsafe S2)
        - 안전한 경우: 오직 'safe'로만 답변하세요.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{text}")
        ])
        
        chain = prompt | self.llm
        judgment_raw = chain.invoke({"text": user_query}).content
        judgment = normalize_content(judgment_raw).strip()
        
        if "unsafe" in judgment:
            print(f"🛡️ [InputSafetyGuardrail] 차단됨: {judgment}")
            return ModelResponse(
                result=[
                    AIMessage(content=f"🛡️ [Safety Guard Blocked] 입력된 질문에 보안 정책 위배({judgment}) 우려가 있어 처리할 수 없습니다.")
                ]
            )
        
        return handler(request)


class TopicAlignmentGuardrail(AgentMiddleware):
    """주제 탈선을 방지하고 비즈니스 대화 범위를 유지하는 미들웨어 (NeMo Guardrails 아키텍처 계승)"""
    def __init__(self, model="gemini-3.5-flash", temperature=0.0):
        self.llm = get_llm(model_name=model, temperature=temperature)
        
    def wrap_model_call(self, request, handler):
        messages = []
        if isinstance(request, dict):
            messages = request.get("messages", [])
        elif hasattr(request, "input_data") and request.input_data:
            messages = request.input_data.get("messages", [])
        elif hasattr(request, "messages") and request.messages:
            messages = request.messages
            
        if not messages:
            return handler(request)
            
        user_query = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
        user_query = normalize_content(user_query)
        
        # 주제 이탈 감지 라우팅 프롬프트
        intent_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 사용자의 질문이 당사 서비스 영역(금융인증서, 일반 업무, 일반 상식)을 
            벗어나는지 판별하는 시맨틱 가드레일 라우터입니다.
            
            특히 아래 주제에 해당하는 경우 무조건 'off_topic'으로 분류하세요:
            - 타사 AI 어시스턴트(빅스비, 클로바, 제미나이, 시리, Alexa 등)에 대한 추천, 성능 비교 및 평가 요청
            - 사외 기밀 유출, 정치, 종교, 자극적인 사회적 논쟁 주제
            
            응답은 반드시 오직 'on_topic' 혹은 'off_topic' 중 단어 하나로만 출력하세요."""),
            ("user", "{text}")
        ])
        
        intent_chain = intent_prompt | self.llm
        intent_result_raw = intent_chain.invoke({"text": user_query}).content
        intent_result = normalize_content(intent_result_raw).strip().lower()
        
        if "off_topic" in intent_result:
            print(f"🛑 [TopicAlignmentGuardrail] 차단됨: 비즈니스 이탈 화제 감지")
            return ModelResponse(
                result=[
                    AIMessage(content="🛑 [Topic Guard Blocked]: 저희는 당사의 서비스 범위에 최적화된 에이전트입니다. 타사 제품이나 외부 어시스턴트에 대한 성능 평가 및 비교 정보는 제공하지 않습니다.")
                ]
            )
            
        return handler(request)


class OutputSchemaRepairGuardrail(AgentMiddleware):
    """출력 데이터의 스키마 유효성을 검증하고 실패 시 자가 수선 유도 (Guardrails AI 아키텍처 계승)"""
    def __init__(self, pydantic_schema, model="gemini-3.5-flash", max_retry=2):
        self.pydantic_schema = pydantic_schema
        self.parser = JsonOutputParser(pydantic_object=pydantic_schema)
        self.llm = get_llm(model_name=model, temperature=0.0)
        self.max_retry = max_retry
        
    def wrap_model_call(self, request, handler):
        response = handler(request)
        
        raw_content = ""
        if hasattr(response, "result") and response.result:
            raw_content = response.result[-1].content
        elif hasattr(response, "content"):
            raw_content = response.content
            
        raw_content = normalize_content(raw_content)
        try:
            self.parser.parse(raw_content)
            return response
        except Exception as parse_error:
            print(f"⚠️ [OutputSchemaRepairGuardrail] 유효성 에러 검출: {parse_error}. 자가 정정(Repair) 시작...")
            
            # 자가 교정 피드백 루프 작동
            feedback_prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 JSON 스키마를 준수하도록 출력을 정제하는 수선기입니다.
                제시된 텍스트를 파싱하려 했으나 다음 에러가 검출되었습니다:
                {error}
                
                아래에 설정된 Pydantic JSON 스키마 규격을 충족하도록 기존 출력을 올바른 JSON 문자열로 전면 수정하여 출력하세요.
                오직 파싱 가능한 순수 JSON 문자열만 출력해야 합니다 (마크다운 백틱 ``` 금지).
                
                Pydantic JSON 스키마:
                {format_instructions}"""),
                ("user", "기존 출력:\n{bad_content}")
            ])
            
            feedback_chain = feedback_prompt | self.llm
            format_instructions = self.parser.get_format_instructions()
            
            for attempt in range(self.max_retry):
                try:
                    repaired_raw_raw = feedback_chain.invoke({
                        "error": str(parse_error),
                        "format_instructions": format_instructions,
                        "bad_content": raw_content
                    }).content
                    repaired_raw = normalize_content(repaired_raw_raw).strip()
                    
                    # 수선된 내용 검증
                    self.parser.parse(repaired_raw)
                    print(f"✅ [OutputSchemaRepairGuardrail] 스키마 자가 교정 성공! (시도: {attempt+1}/{self.max_retry})")
                    
                    if hasattr(response, "result") and response.result:
                        response.result[-1].content = repaired_raw
                    elif hasattr(response, "content"):
                        response.content = repaired_raw
                    return response
                except Exception as retry_err:
                    parse_error = retry_err
                    
            print("🛑 [OutputSchemaRepairGuardrail] 자가 교정 한계 돌파. 스키마 오류를 포함한 원본을 리턴합니다.")
            return response
