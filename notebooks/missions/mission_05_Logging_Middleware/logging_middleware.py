import os
import time
import json
from typing import Any, Dict
from langchain.agents.middleware import AgentMiddleware

class LoggingMiddleware(AgentMiddleware):
    def __init__(self, log_dir="./artifacts/logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        # TODO: 런타임별(요청별) 고유 정보를 격리 저장할 스레드/비동기 세이프한 저장소 생성
        # self._active_runs = {}

    def before_agent(self, state: Dict[str, Any], runtime: Any) -> Dict[str, Any] | None:
        """
        [TODO: Mission 04] 에이전트 전체 실행의 시작을 가로채(Intercept) 로깅합니다.
        1. runtime.context.logging_enabled 가 활성화되어 있는지 확인합니다.
        2. 시작 시간과 사용자 질문 쿼리를 기록(active_runs에 저장)합니다.
        3. 콘솔에 시작 로그를 이쁘게 출력합니다.
        """
        # logging_enabled = getattr(runtime.context, "logging_enabled", False) if runtime and runtime.context else False
        return None

    def after_agent(self, state: Dict[str, Any], runtime: Any) -> Dict[str, Any] | None:
        """
        [TODO: Mission 04] 에이전트 전체 실행의 완료 시점을 가로채 소요 시간(Latency)을 측정하고 감사 로그를 적재합니다.
        1. active_runs에서 해당 runtime 객체의 기록(시작 시간, 질문)을 pop합니다.
        2. 현재 시각과의 차이를 계산하여 duration_ms를 구합니다.
        3. 에이전트의 최종 답변 및 전체 대화 궤적(Dialogue History)을 추출합니다.
        4. session_id를 구하고, _append_log를 호출하여 감사 로그를 세션별 JSON라인 형태로 파일 적재합니다.
        """
        # logging_enabled = getattr(runtime.context, "logging_enabled", False) if runtime and runtime.context else False
        return None

    def wrap_tool_call(self, request, handler):
        """
        [TODO: Mission 04] 개별 도구(Tool Call) 격발의 시작과 완료를 감싸서 로깅합니다.
        1. 도구 실행(handler(request)) 전후의 수행 시간을 구합니다.
        2. session_id를 구하고, 각 도구별 수행 시간을 세션 감사 로그 파일에 기록하며, 실행 결과(response)를 그대로 반환합니다.
        """
        # logging_enabled = getattr(request.runtime.context, "logging_enabled", False) if request.runtime and request.runtime.context else False
        return handler(request)

    def _append_log(self, session_id, log_data):
        """[TODO: Mission 04] 감사 로그 지정 디렉토리 내에 세션별 JSON라인 파일로 적재"""
        # log_file = os.path.join(self.log_dir, f"{session_id}.jsonl")
        pass
