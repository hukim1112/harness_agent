# 🏁 Mission 01: Initial LangChain Agent (Baseline Chatbot)

## 1. 개요 (Overview)
본 미션의 목표는 LangChain의 최신 에이전트 생성 팩토리 함수인 `create_agent`를 활용하여 가장 단순한 형태의 **기초 ReAct 에이전트(Baseline Chatbot)**를 구축하는 것입니다. 이 과정에서 에이전틱 루프(Agent Loop)가 어떻게 구동되는지 이해하고, 런타임 제어 설정을 연동할 수 있는 기반을 다집니다.

---

## 2. 학습 목표 (Learning Objectives)
*   `init_chat_model` 및 `get_llm` 팩토리를 통해 다양한 LLM 공급자(OpenAI, Vertex AI)를 통합 로드하는 방법을 학습합니다.
*   LangChain의 결정론적 에이전트 그래프 빌더인 `create_agent` 패브릭의 파라미터를 이해합니다.
*   에이전트가 도구(Tools) 없이 순수 자연어 추론(Chat)만 수행할 때의 대화 루프 작동 방식을 이해합니다.

---

## 3. 미션 가이드 및 요구사항 (Mission Requirements)

### [태스크 1] 중앙 LLM 팩토리 연동
*   `app/utils/llm.py` 모듈에 있는 `get_llm` 함수를 이용하여 에이전트의 두뇌가 될 `ChatModel`을 생성합니다.
*   기본 모델은 `openai:gpt-4o` 또는 `google_vertexai:gemini-2.5-pro` 중 하나를 선택해 기동합니다.

### [태스크 2] 에이전트 빌드 (`create_agent`)
*   `langchain.agents` 패키지에서 제공하는 `create_agent` 함수를 활용해 에이전트를 빌드합니다.
*   시스템 프로필(System Prompt)은 `app/prompts/__init__.py` 내 정의된 기본 챗봇 프롬프트를 수혈하여 동작하게 만듭니다.
*   도구 리스트(`tools`)는 빈 리스트 `[]`를 바인딩하여 도구 없는 상태로 시작합니다.

### [태스크 3] 에이전트 호출 및 스트리밍 검증
*   구축된 `agent_executor`를 동기 `invoke`와 비동기 `astream_events` 형태로 각각 호출하여 응답이 올바르게 생성되는지 확인합니다.

---

## 4. 실습 코드 가이드 (Jupyter Notebook Skeleton)
`notebooks/missions/mission_01_baseline/skeleton.ipynb` 노트북 파일 내의 `# TODO` 주석 부분을 완성하여 아래 테스트 코드가 성공적으로 통과되도록 만드세요.

### 예시 실행 코드:
```python
from langchain.agents import create_agent
from app.utils.llm import get_llm

# TODO: LLM 및 에이전트 생성
llm = get_llm(model_name="openai:gpt-4o")
agent = create_agent(
    model=llm,
    tools=[],
    system_prompt="You are a helpful assistant."
)

# 실행 및 검증
res = agent.invoke({"messages": [{"role": "user", "content": "안녕하세요!"}]})
print(res["messages"][-1].content)
```
