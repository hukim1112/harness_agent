try:
    from .CHATBOT import CHATBOT_SYSTEM_PROMPT
except ImportError:
    from .chatbot import CHATBOT_SYSTEM_PROMPT

try:
    from .SCRAPER import SCRAPER_SYSTEM_PROMPT
except ImportError:
    from .scraper import SCRAPER_SYSTEM_PROMPT

try:
    from .SUPERVISOR import SUPERVISOR_SYSTEM_PROMPT
except ImportError:
    from .supervisor import SUPERVISOR_SYSTEM_PROMPT

try:
    from .ANALYST import ANALYST_SYSTEM_PROMPT
except ImportError:
    from .analyst import ANALYST_SYSTEM_PROMPT


__all__ = [
    "CHATBOT_SYSTEM_PROMPT",
    "SCRAPER_SYSTEM_PROMPT",
    "SUPERVISOR_SYSTEM_PROMPT",
    "ANALYST_SYSTEM_PROMPT",
]
