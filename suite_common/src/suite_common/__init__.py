"""Shared bits for the Inscription / CaseForge / CaseGuide suite.

Two halves:

- :mod:`suite_common.llm` — OpenAI-compatible chat-completions client used
  by Inscription's step rewriter and CaseGuide's suggestions refiner.
- :mod:`suite_common.coerce` — JSON-tolerant coercion helpers used by every
  app that reads case.json / suggestions.json / manifest.json.
"""

from suite_common.coerce import (
    coerce_bool,
    coerce_int,
    parse_iso,
    parse_optional_iso,
    string_list,
)
from suite_common.llm import (
    DEFAULT_TEMPERATURE,
    ChatClient,
    LLMClient,
    LLMConfigError,
    LLMError,
    LLMRequestError,
    LLMResponseError,
    list_available_models,
)

__all__ = [
    "DEFAULT_TEMPERATURE",
    "ChatClient",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMRequestError",
    "LLMResponseError",
    "coerce_bool",
    "coerce_int",
    "list_available_models",
    "parse_iso",
    "parse_optional_iso",
    "string_list",
]
