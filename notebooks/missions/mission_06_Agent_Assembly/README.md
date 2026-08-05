# Mission 06: Agent Assembly & Production Server Registration

이 미션은 지금까지 개별 단계로 학습하고 구현한 모든 에이전트 컴포넌트(프롬프트 캐싱, 워킹 메모리 체크포인터, 도구 바인딩, 로깅 미들웨어)를 하나로 조립하여, 실제 프로덕션 서버에 등록 가능한 완성형 에이전트(`harness_agent.py`)를 빌드하고 구동하는 최종 통합 과정입니다.

## 🎯 학습 목표
1. **정적/동적 프롬프트 엔진 결합**: `PromptManager` 및 `@dynamic_prompt` 미들웨어를 연동하여 5계층 프롬프트와 캐시 바운더리를 결합합니다.
2. **SQLite 워킹 메모리 구축**: 임시 `MemorySaver` 대신 SQLite 기반 `SqliteSaver`를 결합하여 단기 대화 이력을 안전하게 영속화합니다.
3. **범용 도구 연동**: 8대 범용 챗봇 도구(`tools_chatbot`)를 바인딩하여 실행 루프(ReAct)를 연동합니다.
4. **수명 주기 로깅 및 제어**: `LoggingMiddleware`를 결합하고, `./configs/logging.config` 파일 설정에 따라 로깅 여부가 제어되도록 `AgentContext`와 연동합니다.
5. **FastAPI 서버 레지스트리 포팅**: 완성된 코드를 `app/agents/harness_agent.py`로 포팅하고, `app/agents/__init__.py` 에이전트 등록소(Registry)를 점검하여 서버 및 Web UI에 최종 활성화합니다.

---

## 🚀 에이전트 구동 및 웹 UI 테스트 안내

에이전트가 완성되어 `app/agents/harness_agent.py`에 등록되면, 아래의 안내에 따라 백엔드 서버와 프론트엔드 UI를 실행하여 연동 테스트를 진행할 수 있습니다.

### 1. 가상환경 활성화 및 환경변수 셋업
먼저, 프로젝트에 필요한 패키지들이 설치된 가상환경을 활성화하고 `.env` 설정에 유효한 API Key들이 기입되어 있는지 확인합니다.
```bash
# 가상환경 활성화 (WSL/Ubuntu 기준)
source ~/env_langchain_123/bin/activate

# .env 파일에 필요한 API Key 설정 상태 확인 (Vertex AI, Gemini, OpenAI 등)
cat .env
```

### 2. 백엔드 FastAPI 서버 실행
에이전트의 라이프사이클을 API 엔드포인트로 노출해 주는 FastAPI 서버를 가동합니다.
```bash
# 백엔드 서버 실행
python app/server.py
```
*   서버는 기본적으로 **`http://localhost:8000`** 포트에서 기동합니다.
*   서버 구동 로그에 `✅ Registered agent: harness_agent at /harness_agent`가 정상적으로 표시되는지 확인하십시오.

### 3. 프론트엔드 Streamlit 웹 UI 실행
에이전트와 실시간 대화를 나눌 수 있는 프리미엄 Streamlit 웹 UI 프론트엔드를 실행합니다. (새로운 터미널 창을 열어서 실행)
```bash
# Streamlit 웹 UI 실행
streamlit run app/ui.py
```
*   웹 UI는 기본적으로 **`http://localhost:8501`** 포트에서 브라우저 창으로 자동 열립니다.
*   브라우저가 열리면 사이드바의 **Agent Selection** 메뉴에서 **`harness_agent`**를 선택한 뒤 대화를 진행해 보십시오.
*   `harness_agent`에 추가된 도구(Tools)가 실시간으로 호출되고 그 추론 궤적(Audit Trail)이 콘솔과 웹 UI 하단에 예쁘게 시각화되어 흐르는지 확인합니다.

