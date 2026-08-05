# Mission 07: Self-Correction, Guardrails, Evaluation Harness & Public Skills

이 미션은 에이전트의 안전성을 담보하는 **보안/토픽 가드레일**과 거대 토큰 오버플로우 및 API 통신 오류를 스스로 치유하는 **예외 자가 치유(Self-Correction) 미들웨어**를 조립하고, 자동화된 **평가 하네스(Evaluation Harness)**를 가동하여 검증하는 과정입니다. 

나아가, 깃허브 오픈소스 생태계에 공개된 수백 개의 **공개 에이전트 스킬(Awesome Agent Skills)**을 한 줄의 명령어로 다운로드받아 에이전트에 동적으로 장착 및 구동해 보는 심화 실습을 포함합니다.

## 🎯 학습 목표
1. **입력 보안 필터 (`InputSafetyGuardrail`)**: S1/S2/S3 유해 범죄/해킹 질문을 탐색하여 사전 차단합니다.
2. **비즈니스 토픽 필터 (`TopicAlignmentGuardrail`)**: 에이전트의 서비스 범위를 이탈한 주제(선거/정치 지지 분석 등)를 감지하여 유연하게 거절 답변을 출력합니다.
3. **하이브리드 컨텍스트 인덱서 (`SmartContextIndexer`)**: 15,000자 초과의 대용량 문서 도구 출력 감지 시, 백그라운드 LLM으로 목차(Line Hint)를 자동 생성해 주입하고 에이전트가 `file_read`로 필요한 부분만 핀포인트로 다시 정독하는 지능형 읽기(Progressive Reading) 루프를 구축합니다.
4. **평가 하네스 구축 (Linter + LLM-as-a-Judge)**: Linter와 Judge LLM을 연계하여 가드레일 차단 문구 검출 및 최종 답변 안전성을 100점 만점 지표로 자동 채점합니다.
5. **공개 스킬 다운로드 및 동적 장착 (awesome-agent-skills)**: Vercel Labs의 `npx skills` CLI를 사용해 깃허브 공개 스킬(예: `openai/jupyter-notebook`)을 로컬 `./skills/`에 다운로드받고, 에이전트가 `file_read`와 `bash_command` 기본 도구만으로 스킬을 자율 학습해 수행하도록 프롬프트 엔지니어링을 구성합니다.
