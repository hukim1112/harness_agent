# ⚖️ Mission 06: LLM-as-Judge & Hill-Climbing

## 1. 개요 (Overview)
에이전트가 배포된 후에도 프롬프트나 파라미터가 조정됨에 따라 답변의 질이 개선되는지 퇴보하는지(Regression) 신속하고 정량적으로 측정할 수 있어야 합니다. 본 미션의 목표는 에이전트의 답변을 LLM이 직접 공정하게 평가하는 **`LLM-as-a-Judge`** 패턴을 구현하고, 평가 점수를 바탕으로 프롬프트를 피드백 루프에 따라 점진적으로 최적화하는 **힐클라이밍(Hill-Climbing) 최적화 하네스**를 설계 및 실습하는 것입니다.

---

## 2. 학습 목표 (Learning Objectives)
*   평가 하네스의 필수 요소인 평가자 LLM(Judge LLM), 기준 데이터셋(Golden Dataset), 평가 스키마의 작동 방식을 학습합니다.
*   다단계 검증(Correctness, Completeness, Tone & Style)을 수행하는 LLM 판사 프롬프트를 디자인하고 점수를 도출하는 기법을 배웁니다.
*   점수를 향상시키기 위해 이전 평가의 피드백을 프롬프트에 자동으로 반영하여 고도화하는 힐클라이밍 최적화 루프를 설계합니다.

---

## 3. 미션 가이드 및 요구사항 (Mission Requirements)

### [태스크 1] Golden Dataset 정의 및 Generator 실행
*   간단한 질문과 정답 기준을 포함하는 3~5개 샘플 규모의 **Golden Dataset**을 파이썬 사전 형태로 구성합니다.
*   에이전트(Generator)를 기동하여 이 질문셋에 대해 각각 답변을 생성하도록 호출합니다.

### [태스크 2] LLM-as-a-Judge 평가기 구현
*   생성된 답변과 Golden Dataset의 모범 답안을 비교하여 1점부터 5점까지 점수를 매기는 **`Judge LLM`**을 구현합니다.
*   점수와 정성적인 피드백(사유)을 포함하는 정형화된 JSON 형식을 반환하도록 구조화합니다.

### [태스크 3] Hill-Climbing 프롬프트 최적화 루프 설계
*   1차 평가의 평균 점수와 정성적 사유를 바탕으로 에이전트의 프롬프트 지침을 수정합니다.
*   수정된 프롬프트를 에이전트(Generator)에 다시 주입하고 재평가를 실시하여 점수가 상승(힐클라이밍)하는지 확인하는 자동화 루프를 구동합니다.

---

## 4. 실습 코드 가이드 (Jupyter Notebook Skeleton)
`notebooks/missions/mission_06_evaluation/skeleton.ipynb` 노트북 파일 내 빈 칸들을 채워 평가 및 프롬프트 최적화 파이프라인을 완성하세요.
