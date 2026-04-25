"""LLM-backed step rewriting.

Inscription records a reliable but robotic step list — *"Click the 'Save'
Button in Notepad."*. A local language model can take that timeline plus
the raw UIA context and rewrite it as natural procedural documentation —
*"Save the file by choosing File → Save As."* — merging related events
into one sentence where it makes sense.

The pipeline targets any OpenAI-compatible chat-completions endpoint:
Ollama (default), LM Studio, ``llama.cpp --server``, or a remote service.
``LLMClient`` talks to the endpoint; ``StepRewriter`` orchestrates the
session read → prompt → parse → write loop. The Qt controller spins this
up on a worker thread and falls back to the rule-based text on any
failure, so the editor never gets stuck.
"""

from inscription.llm.client import (
    DEFAULT_TEMPERATURE,
    ChatClient,
    LLMClient,
    LLMConfigError,
    LLMError,
    LLMRequestError,
    LLMResponseError,
)
from inscription.llm.prompt import SYSTEM_PROMPT, RewrittenStep, build_user_prompt, parse_response
from inscription.llm.rewriter import StepRewriter

__all__ = [
    "DEFAULT_TEMPERATURE",
    "SYSTEM_PROMPT",
    "ChatClient",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMRequestError",
    "LLMResponseError",
    "RewrittenStep",
    "StepRewriter",
    "build_user_prompt",
    "parse_response",
]
