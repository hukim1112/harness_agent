# 🛠️ Mission 03: Common Tools Integration

## 1. 개요 (Overview)
에이전트가 코드를 분석하거나 시스템 명령을 실행하고, 웹 검색을 수행하기 위해서는 외부 리소스와 상호작용할 수 있는 **도구(Tools)**가 필수적입니다. Claude Code가 자랑하는 8대 범용 도구(파일 읽기/쓰기/편집, 셸 명령 실행, Grep/Glob 검색, 웹 검색/가져오기)가 어떻게 선언되고 구현되어 있는지 이해하고, 이를 에이전트에 직접 연동하여 자율적 업무 수행 능력을 극대화하는 것이 본 미션의 목표입니다.

---

## 2. 학습 목표 (Learning Objectives)
*   LangChain의 `@tool` 데코레이터를 이용해 일반 파이썬 함수를 LLM이 이해하는 도구 명세(Schema)로 변환하는 메커니즘을 파악합니다.
*   Claude Code 및 Hermes Agent의 실무 도구 구현(파일 검색, 셸 명령어 안전 격발, 웹 크롤링)을 이해합니다.
*   다양한 도구가 바인딩된 에이전트가 사용자 질의에 맞춰 자율적으로 도구를 선택하고 실행(Thought ➔ Action ➔ Observation)하는 ReAct 루프를 검증합니다.

---

## 3. 미션 가이드 및 요구사항 (Mission Requirements)

### [태스크 1] 범용 도구 리스트 임포트 및 파악
*   `app/tools/common.py`에 선언된 다음 핵심 도구들의 명세(Docstring 및 파라미터 타입)를 읽고 분석합니다.
    *   **파일 운영:** `file_read`, `file_edit`, `file_writer`, `notebook_edit`
    *   **셸 명령:** `bash_command` (Timeout 및 stdout 제한 구현)
    *   **검색 필터:** `grep_search`, `glob_search`
    *   **웹 브라우징:** `web_fetch`, `web_search`

### [태스크 2] 에이전트에 도구 연결
*   에이전트 생성 시 `tools` 리스트 인자에 위에 정의된 범용 도구 세트(`tools_chatbot` 또는 개별 도구 조합)를 전달하여 바인딩합니다.

### [태스크 3] 자율 도구 실행(ReAct) 검증
*   도구 실행이 필요한 여러 시나리오의 질문을 에이전트에 던지고, 에이전트가 알맞은 도구를 스스로 골라 실행하여 정답을 추출해내는지 검증합니다.
    *   *테스트 1:* "프로젝트 루트 폴더 내에 `.env` 파일이 있는지 glob_search 도구로 검색해줘."
    *   *테스트 2:* "`app/server.py` 파일의 1줄부터 20줄까지 읽어서 보여줘."
    *   *테스트 3:* "현재 리눅스 환경의 사용자 정보(whoami)를 bash_command로 확인해줘."

---

## 4. 실습 코드 가이드 (Jupyter Notebook Skeleton)
`notebooks/missions/mission_03_common_tools/skeleton.ipynb` 노트북 파일의 가이드를 따라 미션을 완료하세요.
