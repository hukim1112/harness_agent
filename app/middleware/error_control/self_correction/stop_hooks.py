"""
===============================================================================
[Error Control / Self-Correction] Stop Hooks Middleware
===============================================================================
LLM의 출력 품질을 검증하고, 결함 발견 시 피드백을 주입하여
에이전트가 스스로 버그를 수정하도록 유도하는 인루프 자가 교정 미들웨어.

Claude Code의 StopHook 아키텍처 구현:
  - 에이전트 응답 내 코드 블록을 AST/compile()로 문법 검증
  - 검증 실패 시 blockingError 피드백을 HumanMessage로 주입
  - 에이전트가 다음 턴에서 수정된 코드를 재생성 (Self-Repair Loop)

참조:
  - Claude Code: query.ts → stop_hook_blocking transition
===============================================================================
"""

import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents.middleware import AgentMiddleware


def extract_code_blocks(text: str) -> list[str]:
    """텍스트에서 모든 Python 코드 블록을 추출합니다."""
    pattern = re.compile(r"```(?:python)?\s*(.*?)\s*```", re.DOTALL)
    return pattern.findall(text)


# =============================================================================
# StopHooksMiddleware (Self-Correction via Output Validation)
# =============================================================================
class StopHooksMiddleware(AgentMiddleware):
    """에이전트 응답 내 코드 블록을 검증하고, 실패 시 수정 피드백을 주입합니다.

    검증기(Validator)를 플러그인 방식으로 확장할 수 있습니다.
    기본값은 Python 문법(Syntax) 검증기입니다.

    Args:
        validators: 검증기 리스트. 각 항목은 {"name": str, "fn": Callable} 딕셔너리.
                    fn은 코드 문자열을 받아 에러 메시지(str) 또는 None을 반환합니다.

    Example:
        ```python
        from app.middleware.error_control.self_correction import StopHooksMiddleware

        # 기본 Python 문법 검증
        middleware = StopHooksMiddleware()

        # 커스텀 검증기 추가
        def check_no_eval(code: str) -> str | None:
            if "eval(" in code:
                return "Security: eval() 사용 금지"
            return None

        middleware = StopHooksMiddleware(validators=[
            {"name": "python_syntax", "fn": check_python_syntax},
            {"name": "no_eval", "fn": check_no_eval},
        ])
        ```
    """

    def __init__(self, validators: Optional[list[dict[str, Any]]] = None):
        if validators is None:
            def check_python_syntax(code_str: str) -> Optional[str]:
                try:
                    compile(code_str, "<string>", "exec")
                    return None
                except SyntaxError as e:
                    return f"SyntaxError at line {e.lineno}: {e.msg} -> '{e.text.strip() if e.text else ''}'"
                except Exception as e:
                    return f"Code validation error: {e}"

            self.validators = [{"name": "python_syntax", "fn": check_python_syntax}]
        else:
            self.validators = validators

    def after_agent(self, state: dict, runtime=None) -> dict | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage) or not last_msg.content:
            return None

        from app.utils.message_utils import normalize_content
        content_str = normalize_content(last_msg.content)
        code_blocks = extract_code_blocks(content_str)
        if not code_blocks:
            return None

        validation_errors = []
        for code in code_blocks:
            for val in self.validators:
                val_name = val.get("name", "unknown")
                val_fn = val.get("fn")
                if val_fn:
                    try:
                        error = val_fn(code)
                        if error:
                            validation_errors.append(f"[{val_name}]: {error}")
                    except Exception as e:
                        validation_errors.append(f"[{val_name}] execution error: {e}")

        if validation_errors:
            error_details = "\n".join(validation_errors)
            correction_prompt = (
                f"🛑 [Stop Hook Blocking - Code Validation Failed]\n"
                f"The code you generated failed quality validation tests:\n"
                f"{error_details}\n\n"
                f"Please analyze the error details above, fix the bug in your code, and output the corrected version."
            )
            print(f"\n🔴 [stop_hook_blocking] Validation Failed -> Injecting blockingError for Self-Repair!")
            updated_messages = list(messages) + [HumanMessage(content=correction_prompt)]
            return {"messages": updated_messages, "transition": "stop_hook_blocking"}

        return {"transition": "completed"}
