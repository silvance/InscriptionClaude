"""LLM augmentation for CaseGuide suggestions.

The deterministic playbook matcher produces a high-quality starting list.
The LLM augmentation pass takes that list plus the case scope and (a)
prunes anything the model judges irrelevant, (b) tailors the wording to
the specific scope, and (c) optionally adds scope-specific suggestions
that no playbook covered. The model never invents from scratch — it works
from the playbook output as ground truth.
"""

from suite_common.llm import LLMClient, LLMError

from caseguide.llm.augment import SuggestionsRefiner

__all__ = ["LLMClient", "LLMError", "SuggestionsRefiner"]
