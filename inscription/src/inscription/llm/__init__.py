"""LLM-backed step rewriting.

Inscription records a reliable but robotic step list — *"Click the 'Save'
Button in Notepad."*. A local language model can take that timeline plus
the raw UIA context and rewrite it as natural procedural documentation —
*"Save the file by choosing File → Save As."* — merging related events
into one sentence where it makes sense.

The pipeline targets any OpenAI-compatible chat-completions endpoint:
Ollama (default), LM Studio, ``llama.cpp --server``, or a remote service.
"""

from suite_common.llm import LLMClient, LLMError

from inscription.llm.rewriter import StepRewriter

__all__ = ["LLMClient", "LLMError", "StepRewriter"]
