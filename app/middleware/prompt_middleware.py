from langchain.agents.middleware import dynamic_prompt
from app.prompts.prompt_manager import build_harness_agent_prompt

# 🌟 @dynamic_prompt 데코레이터가 적용된 프로덕션 규격 프롬프트 미들웨어 객체
harness_agent_prompt_middleware = dynamic_prompt(build_harness_agent_prompt)
