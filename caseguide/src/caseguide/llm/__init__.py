"""LLM augmentation for CaseGuide suggestions.

The deterministic playbook matcher produces a high-quality starting
list. The LLM augmentation pass takes that list plus the case scope
and (a) prunes anything the model judges irrelevant, (b) tailors the
wording to the specific scope, and (c) optionally adds scope-specific
suggestions that no playbook covered.

The model never invents from scratch — it works from the playbook
output as ground truth. That keeps the LLM's role focused and the
output predictable.
"""

from caseguide.llm.augment import SuggestionsRefiner
from caseguide.llm.client import (
    ChatClient,
    LLMClient,
    LLMConfigError,
    LLMError,
    LLMRequestError,
    LLMResponseError,
)
from caseguide.llm.prompt import SYSTEM_PROMPT, build_user_prompt, parse_response

__all__ = [
    "SYSTEM_PROMPT",
    "ChatClient",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMRequestError",
    "LLMResponseError",
    "SuggestionsRefiner",
    "build_user_prompt",
    "parse_response",
]
