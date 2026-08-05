# Mission 07: Self-Correction, Guardrails & Evaluation Harness

이 미션은 에이전트의 안전성을 담보하는 **보안/토픽 가드레일**과 거대 토큰 오버플로우 및 API 통신 오류를 스스로 치유하는 **예외 자가 치유(Self-Correction) 미들웨어**를 조립하고, 자동화된 **평가 하네스(Evaluation Harness)**를 가동하여 검증하는 과정입니다.

## 🎯 학습 목표
1. **입력 보안 필터 (`InputSafetyGuardrail`)**: S1/S2/S3 유해 범죄/해킹 질문을 탐색하여 사전 차단합니다.
2. **비즈니스 토픽 필터 (`TopicAlignmentGuardrail`)**: 에이전트의 서비스 범위를 이탈한 주제(선거/정치 지지 분석 등)를 감지하여 유연하게 거절 답변을 출력합니다.
3. **하이브리드 컨텍스트 인덱서 (`SmartContextIndexer`)**: 15,000자 초과의 대용량 문서 도구 출력 감지 시, 백그라운드 LLM으로 목차(Line Hint)를 자동 생성해 주입하고 에이전트가 `view_file_lines`로 필요한 부분만 핀포인트로 다시 정독하는 지능형 읽기(Progressive Reading) 루프를 구축합니다.
4. **평가 하네스 구축 (Linter + LLM-as-a-Judge)**:
   * **Linter (규칙 검사)**: 차단 문구의 포함 여부와 도구 격발 turn 수 제한 등의 동작 결과를 결정론적으로 자동 채점합니다.
   * **LLM-as-a-Judge (AI 채점)**: 최종 응답의 안전성, 정확성, 가독성을 판정 LLM이 읽어 0~100 점수로 평가하고 판정 결과표를 출력합니다.
