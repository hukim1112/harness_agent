import os
import json
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

class InputSafetyGuardrail(AgentMiddleware):
    """입력 유해 규정 검사 보안 필터 미들웨어 (Llama Guard 아키텍처 계승)"""
    def __init__(self, model="gpt-4o", temperature=0.0):
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        
    def wrap_call(self, request, handler):
        messages = request.input_data.get("messages", [])
        if not messages:
            return handler(request)
            
        user_query = messages[-1].content
        
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
        judgment = chain.invoke({"text": user_query}).content.strip()
        
        if "unsafe" in judgment:
            print(f"🛡️ [InputSafetyGuardrail] 차단됨: {judgment}")
            return {
                "messages": [
                    AIMessage(content=f"🛡️ [Safety Guard Blocked] 입력된 질문에 보안 정책 위배({judgment}) 우려가 있어 처리할 수 없습니다.")
                ]
            }
        
        return handler(request)


class TopicAlignmentGuardrail(AgentMiddleware):
    """주제 탈선을 방지하고 비즈니스 대화 범위를 유지하는 미들웨어 (NeMo Guardrails 아키텍처 계승)"""
    def __init__(self, model="gpt-4o", temperature=0.0):
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        
    def wrap_call(self, request, handler):
        messages = request.input_data.get("messages", [])
        if not messages:
            return handler(request)
            
        user_query = messages[-1].content
        
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
        intent_result = intent_chain.invoke({"text": user_query}).content.strip().lower()
        
        if "off_topic" in intent_result:
            print(f"🛑 [TopicAlignmentGuardrail] 차단됨: 비즈니스 이탈 화제 감지")
            return {
                "messages": [
                    AIMessage(content="🛑 [Topic Guard Blocked]: 저희는 당사의 서비스 범위에 최적화된 에이전트입니다. 타사 제품이나 외부 어시스턴트에 대한 성능 평가 및 비교 정보는 제공하지 않습니다.")
                ]
            }
            
        return handler(request)


class OutputSchemaRepairGuardrail(AgentMiddleware):
    """출력 데이터의 스키마 유효성을 검증하고 실패 시 자가 수선 유도 (Guardrails AI 아키텍처 계승)"""
    def __init__(self, pydantic_schema, model="gpt-4o", max_retry=2):
        self.pydantic_schema = pydantic_schema
        self.parser = JsonOutputParser(pydantic_object=pydantic_schema)
        self.llm = ChatOpenAI(model=model, temperature=0.0)
        self.max_retry = max_retry
        
    def wrap_call(self, request, handler):
        response = handler(request)
        
        if not response or "messages" not in response:
            return response
            
        last_msg_content = response["messages"][-1].content
        current_output = last_msg_content
        
        for attempt in range(1, self.max_retry + 1):
            try:
                parsed_data = self.parser.parse(current_output)
                response["messages"][-1].content = json.dumps(parsed_data, ensure_ascii=False)
                return response
                
            except Exception as e:
                print(f"❌ [OutputSchemaRepairGuardrail Failed] (Attempt #{attempt}): {e}")
                if attempt == self.max_retry:
                    response["messages"][-1].content = f"❌ [Schema Repair Failure] 데이터 규격 수선 한도를 초과했습니다. 원인: {e}"
                    return response
                
                format_instructions = self.parser.get_format_instructions()
                re_ask_prompt = f"""
                당신이 이전에 생성한 데이터는 검증기에서 에러가 발생했습니다.
                오류 메시지를 참조하여 지시된 Pydantic JSON 구조에 맞춰 재작성해서 온전한 JSON 문자열로만 응답하세요.
                
                이전 결과물:
                {current_output}
                
                오류 원인:
                {e}
                
                출력 형식:
                {format_instructions}
                """
                
                re_ask_response = self.llm.invoke(re_ask_prompt)
                current_output = re_ask_response.content.strip()
                
        return response
