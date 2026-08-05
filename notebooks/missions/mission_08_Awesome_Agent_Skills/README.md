# Mission 08: Awesome Agent Skills & Dynamic Skill Loading

이 미션은 Vercel Labs의 **`npx skills`** CLI와 **awesome-agent-skills (agent-skill.co)** 오픈소스 레지스트리를 연계하여, 깃허브 상에 공개된 검증된 스킬셋을 한 줄의 명령어로 프로젝트에 동적으로 추가하고 에이전트가 이를 자율적으로 학습해 기동하도록 연동하는 실습입니다.

## 🎯 학습 목표
1. **오픈소스 스킬 다운로드 및 파싱**: Vercel의 `npx skills` 패키지 매니저를 통해 공개 깃허브 스킬(예: `openai/jupyter-notebook`)을 로컬 디렉토리(`./skills/`)에 추가합니다.
2. **점진적 스킬 노출 (Progressive Skill Disclosure) 설계**: 에이전트에 많은 도구를 직접 등록하지 않고, 파일 읽기(`file_read`)와 셸 명령어 실행(`bash_command`)이라는 2가지 기본 도구만 쥐어준 ReAct 에이전트를 빌드합니다.
3. **자율적 스킬 학습 및 수행**: 에이전트가 다운로드받은 스킬 가이드 문서(`Skill.md`)를 스스로 정독해 필요한 인자값과 파이썬 스크립트 실행 경로를 파악하고, `bash_command`를 격발해 주피터 노트북 파일(`artifacts/sum_1_to_100.ipynb`)을 자동 생성해내는 과정을 검증합니다.
