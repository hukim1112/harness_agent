# 🗂️ Mission 05: Multi-layered Prompt & Cache

## 1. 개요 (Overview)
에이전트가 복잡한 업무를 장기적으로 수행할 때, 시스템 프롬프트(System Instruction)와 컨텍스트(Dialogue History, Tools Specs)의 크기가 급격히 커지게 됩니다. 이는 LLM 호출 마다 막대한 토큰 비용과 지연 시간(Latency)을 초래합니다. 본 미션의 목표는 시스템 프롬프트를 계층별(L1~L5)로 나누어 모듈화하여 관리하는 **`PromptManager`**를 구현하고, Vertex AI / Gemini 환경에서 제공하는 **프롬프트 캐싱(Prompt Caching / Context Caching)** 기술을 접목하여 운영 비용과 속도를 극적으로 최적화하는 아키텍처를 실습하는 것입니다.

---

## 2. 학습 목표 (Learning Objectives)
*   에이전트의 프롬프트를 L1(역할), L2(지침/가이드라인), L3(사용 가능 도구), L4(동적 메모리/컨텍스트), L5(사용자 발화) 계층으로 구분하여 모듈화하는 설계 기법을 학습합니다.
*   프롬프트 내용의 정적 부분과 동적 부분을 분리하여, 변하지 않는 대형 컨텍스트 영역을 캐시(Cache)로 지정해 비용을 최대 90% 이상 감축하는 원리를 이해합니다.
*   LangChain Google Vertex AI 통합본에서 컨텍스트 캐싱(Context Caching)을 활용하는 법을 배웁니다.

---

## 3. 미션 가이드 및 요구사항 (Mission Requirements)

### [태스크 1] 계층화된 `PromptManager` 구현
*   **L1 (System Role):** 에이전트의 페르소나 및 핵심 정체성 정의
*   **L2 (Operating Guidelines):** 행동 준수 사항 및 금지 행위 지침
*   **L3 (Dynamic Tools Spec):** 현재 바인딩된 도구들의 가용 정보와 스펙 명세
*   **L4 (Context & State):** 사용자 세션 정보 및 워킹 메모리
*   **L5 (User Input):** 현재 시점의 사용자 질문 및 이전 발화

*   `PromptManager`는 각 계층별 프롬프트 블록을 조합하여 최종 프롬프트를 렌더링해야 합니다.

### [태스크 2] 프롬프트 캐싱 설정 및 검증
*   작성한 프롬프트 매니저를 활용하여 대량의 정적 참고 문서(Context)를 프롬프트 상단(L4)에 로드합니다.
*   Vertex AI의 컨텍스트 캐시 생성 기법(Gemini Context Cache API)을 모사하거나 연동하여 캐싱 지점을 선언합니다.
*   에이전트를 생성할 때 대규모 컨텍스트를 캐싱하여 첫 호출(Cold Start) 대비 두 번째 호출(Warm Start)의 지연 시간 단축 효과를 시뮬레이션 및 측정합니다.

### [태스크 3] 서버 연동 및 배포
*   완성한 프롬프트 계층화 매니저를 `app/middleware/` 또는 `app/utils/` 영역에 결합하여 서버 기동 시 에이전트의 프롬프트가 동적으로 구성되도록 적용합니다.

---

## 4. 실습 코드 가이드 (Jupyter Notebook Skeleton)
`notebooks/missions/mission_05_prompt_caching/skeleton.ipynb` 노트북 파일 내 빈 칸들을 채워 프롬프트 빌더 및 캐싱 로직을 완성하세요.
