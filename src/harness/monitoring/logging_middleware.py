import os
import time
import json
from langchain.agents.middleware import AgentMiddleware

class LoggingMiddleware(AgentMiddleware):
    def __init__(self, log_path="./artifacts/agent_audit_trail.json"):
        self.log_path = log_path
        # 로그 파일이 저장될 부모 디렉토리 자동 생성
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def wrap_call(self, request, handler):
        """에이전트 전체 실행의 시작과 완료를 감싸서 로깅"""
        start_time = time.time()
        user_query = request.input_data.get("messages", [])[-1].content
        
        print(f"\n🪵 [LoggingMiddleware] === 에이전트 실행 시작 ===")
        print(f"📥 사용자 질문: {user_query}")
        
        # 에이전트 실행 수행 (전체 대화 루프 수행)
        response = handler(request)
        
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"📤 에이전트 실행 완료 (소요: {duration_ms}ms)")
        
        # 에이전트 최종 답변 및 전체 대화 궤적 추출
        agent_response = ""
        dialogue_history = []
        if response and "messages" in response:
            agent_response = response["messages"][-1].content
            # 전체 메시지 히스토리 조립 (role과 content 추출)
            for msg in response["messages"]:
                dialogue_history.append({
                    "role": msg.type, # 'human', 'ai', 'tool' 등
                    "content": str(msg.content)
                })
        
        # 에이전트 감사 로그 생성 및 파일 적재 (대화 히스토리 및 최종 답변 동봉!)
        audit_log = {
            "event": "agent_execution",
            "session_id": request.config.get("configurable", {}).get("thread_id", "unknown"),
            "query": user_query,
            "response": agent_response,
            "dialogue_history": dialogue_history,  # <-- 특정 세션 하의 전체 대화 궤적 적재!
            "latency_ms": duration_ms,
            "status": "SUCCESS" if response else "FAILED",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        self._append_log(audit_log)
        return response

    def wrap_tool_call(self, request, handler):
        """개별 도구(Tool Call) 격발의 시작과 완료를 감싸서 로깅"""
        tool_name = request.tool_call.get("name", "unknown_tool")
        tool_args = request.tool_call.get("args", {})
        start_time = time.time()
        
        print(f"🔧 [LoggingMiddleware] ➡️ 도구 격발 시작: {tool_name}({tool_args})")
        
        # 도구 실행 수행
        response = handler(request)
        
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"🔧 [LoggingMiddleware] ⬅️ 도구 격발 완료: {tool_name} (소요: {duration_ms}ms)")
        
        # 도구 격발 전용 감사 로그 생성 및 파일 적재
        session_id = "unknown"
        if hasattr(request, "runtime") and hasattr(request.runtime, "config"):
            session_id = request.runtime.config.get("configurable", {}).get("thread_id", "unknown")
            
        tool_log = {
            "event": "tool_execution",
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": tool_args,
            "latency_ms": duration_ms,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        self._append_log(tool_log)
        return response

    def _append_log(self, log_data):
        """감사 로그 지정 경로에 JSON 추가 적재"""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
