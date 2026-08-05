# 💾 Mission 02: SQLite Checkpointer (Episodic Memory L1)

## 1. 개요 (Overview)
기본적인 LangChain 에이전트는 대화 기록을 RAM 메모리(`MemorySaver`)에 저장합니다. 이 경우 애플리케이션이나 서버가 재부팅되면 모든 대화 역사(체크포인트)가 유실됩니다. 본 미션의 목표는 LangGraph의 **`SqliteSaver`**를 사용하여 대화의 1차 영속 메모리(L1 Episodic Memory)를 구축하고 데이터베이스 기반의 영구 세션 관리 기능을 에이전트에 통합하는 것입니다.

---

## 2. 학습 목표 (Learning Objectives)
*   임시 메모리 저장소와 영속성 데이터베이스 기반 체크포인터의 차이점을 파악합니다.
*   파이썬의 `sqlite3` 라이브러리를 멀티 스레드 세이프(`check_same_thread=False`)하게 연결하여 `SqliteSaver`를 구성하는 방법을 학습합니다.
*   동일한 `thread_id`를 전달했을 때, 프로세스 재시작 후에도 대화 맥락이 온전하게 복원되는지 검증합니다.

---

## 3. 미션 가이드 및 요구사항 (Mission Requirements)

### [태스크 1] 데이터베이스 연결 및 체크포인터 셋업
*   `app/database/` 경로 하위에 `checkpoints.db` 데이터베이스 파일을 생성합니다.
*   멀티 스레드 환경(FastAPI 등)에서도 안전하게 데이터베이스 조작을 수행할 수 있도록 `sqlite3.connect` 옵션 중 `check_same_thread=False`를 반드시 설정합니다.
*   생성한 커넥션을 `SqliteSaver` 클래스로 랩핑하여 체크포인터 객체로 만듭니다.

### [태스크 2] 에이전트에 영속 체커바인더 바인딩
*   에이전트 빌더 호출 시, `checkpointer=memory` 인자에 방금 생성한 `SqliteSaver` 객체를 바인딩합니다.

### [태스크 3] 프로세스 독립성(Persistence) 검증
*   임의의 `thread_id`를 지정해 에이전트와 질문-답변을 수행합니다 (예: "내 이름은 김철수야").
*   파이썬 인터프리터(또는 노트북 커널)를 재부팅합니다.
*   커널이 리셋된 후, 동일한 `thread_id`를 지정하고 "내 이름이 뭔지 기억나?"라고 물어보았을 때 에이전트가 정상적으로 과거 기억을 출력하는지 확인합니다.

---

## 4. 실습 코드 가이드 (Jupyter Notebook Skeleton)
`notebooks/missions/mission_02_sqlite_checkpointer/skeleton.ipynb` 노트북 내의 빈 칸을 완성해 나가며 영속화 테스트를 성공적으로 완수하세요.
