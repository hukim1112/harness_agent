# Mission 06: Agent Assembly & Production Server Registration

이 미션은 지금까지 개별 단계로 학습하고 구현한 모든 에이전트 컴포넌트(프롬프트 캐싱, 워킹 메모리 체크포인터, 도구 바인딩, 로깅 미들웨어)를 하나로 조립하여, 실제 프로덕션 서버에 등록 가능한 완성형 에이전트(`harness_agent.py`)를 빌드하고 구동하는 최종 통합 과정입니다.

## 🎯 학습 목표
1. **정적/동적 프롬프트 엔진 결합**: `PromptManager` 및 `@dynamic_prompt` 미들웨어를 연동하여 5계층 프롬프트와 캐시 바운더리를 결합합니다.
2. **SQLite 워킹 메모리 구축**: 임시 `MemorySaver` 대신 SQLite 기반 `SqliteSaver`를 결합하여 단기 대화 이력을 안전하게 영속화합니다.
3. **범용 도구 연동**: 8대 범용 챗봇 도구(`tools_chatbot`)를 바인딩하여 실행 루프(ReAct)를 연동합니다.
4. **수명 주기 로깅 및 제어**: `LoggingMiddleware`를 결합하고, `./configs/logging.config` 파일 설정에 따라 로깅 여부가 제어되도록 `AgentContext`와 연동합니다.
5. **FastAPI 서버 레지스트리 포팅**: 완성된 코드를 `app/agents/harness_agent.py`로 포팅하고, `app/agents/__init__.py` 에이전트 등록소(Registry)를 점검하여 서버 및 Web UI에 최종 활성화합니다.
