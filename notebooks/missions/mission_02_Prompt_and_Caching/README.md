# 🗂️ Mission 02: Multi-layered Prompt & Cache

## 1. 개요 (Overview)
에이전트가 복잡한 업무를 장기적으로 수행할 때, 시스템 프롬프트(System Instruction)와 컨텍스트(Dialogue History, Tools Specs)의 크기가 급격히 커지게 됩니다. 이는 LLM 호출마다 막대한 토큰 비용과 지연 시간(Latency)을 초래합니다. 본 미션의 목표는 시스템 프롬프트를 **Claude Code 표준 5계층(L1~L5)**으로 나누어 모듈화하여 관리하는 **`PromptManager`**를 구현하고, **프롬프트 캐싱(Prompt Caching / Context Caching)** 기술을 접목하여 운영 비용과 속도를 극적으로 최적화하는 아키텍처를 실습하는 것입니다.

---

## 2. 학습 목표 (Learning Objectives)
*   에이전트의 시스템 프롬프트를 **Layer 1(시스템 정체성)**, **Layer 2(도구 스펙 & 스킬 카탈로그)**, **Layer 3(동적 실행 환경)**, **Layer 4(기억 및 동적 컨텍스트)**, **Layer 5(로컬 프로젝트 규칙)** 계층으로 구분하여 모듈화하는 설계 기법을 학습합니다.
*   프롬프트 내용의 정적 부분(L1~L2)과 동적 부분(L3~L5)을 분리하여, 변하지 않는 대형 컨텍스트 영역을 캐시(Cache)로 지정해 비용을 최대 90% 이상 감축하고 레이턴시를 3배 이상 개선하는 원리를 이해합니다.
*   `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 경계선 마커를 활용한 멀티 프로젝트 캐시 보호 및 가드레일 설계법을 배웁니다.

---

## 3. 미션 가이드 및 요구사항 (Mission Requirements)

### [태스크 1] Claude Code 표준 5계층 `PromptManager` 구현
*   **[정적 캐싱 영역 (Static Prefix — Cache HIT 대상)]**
    *   **Layer 1 (System Identity & Core Role):** 에이전트의 페르소나 및 핵심 정체성 정의 (`PROMPT.md` 기반)
    *   **Layer 2 (Tool Capabilities & Skills Catalog):** 바인딩된 도구들의 가용 정보와 스펙 명세 (`request.tools`) 및 `SkillPromptBuilder`가 생성한 스킬 인덱스 카탈로그
    *   **`__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__`:** 캐시 컷오프 경계선 마커 (경계선 상단이 GPU 메모리에 영구 캐싱됨)
*   **[동적 비캐싱 영역 (Dynamic Suffix — Uncached 대상)]**
    *   **Layer 3 (Dynamic Session Environment):** 동적 실행 환경 및 권한 상태 (사용자 권한, 작업 디렉토리 `CWD`, 타겟 프로젝트 정보)
    *   **Layer 4 (Recalled Memory & Dynamic Context):** 소환된 에피소드 기억 및 동적 세션 문서 (Hermes 장기 기억 연동 및 `MCP.md`)
    *   **Layer 5 (User & Project Rules):** `AGENT.md` 프로젝트 로컬 행동 강령 (멀티 프로젝트 전환 시 캐시 오염을 막기 위해 경계선 아래 배치)

> [!NOTE]
> **대화 이력과 사용자 질문의 분리**
> 대화 이력(Dialogue History)과 현재 사용자 발화(User Query)는 LangChain/LangGraph 아키텍처 상 메시지 객체 리스트(`messages`)의 **`HumanMessage`**로 전달되므로, 시스템 지시문 문자열 내부가 아닌 LLM 메시지 스택으로 독립 관리됩니다.

*   `PromptManager`는 각 계층별 프롬프트 블록을 조합하여 최종 시스템 프롬프트를 렌더링해야 합니다.

### [태스크 2] 프롬프트 캐싱 설정 및 검증
*   작성한 프롬프트 매니저를 활용하여 대량의 정적 참고 문서(Context)를 프롬프트 정적 영역(Layer 2 하단 / Static Reference)에 로드합니다.
*   에이전트를 생성할 때 대규모 컨텍스트를 캐싱하여 첫 호출(Cold Start) 대비 두 번째 호출(Warm Start)의 지연 시간 단축 효과를 시뮬레이션 및 측정합니다.

### [태스크 3] 서버 연동 및 배포
*   완성한 프롬프트 계층화 매니저를 `app/middleware/` 또는 `app/prompts/` 영역에 결합하여 서버 기동 시 에이전트의 프롬프트가 동적으로 구성되도록 적용합니다.

---

## 4. 실습 코드 가이드 (Jupyter Notebook Skeleton)
`notebooks/missions/mission_02_Prompt_and_Caching/skeleton.ipynb` 노트북 파일 내 빈 칸들을 채워 프롬프트 빌더 및 캐싱 로직을 완성하세요.
