"""Suggestions refinement: deterministic drafts → LLM-tailored output.

:class:`SuggestionsRefiner` is the bridge between the deterministic
generator and the chat client. The caller hands it a case scope plus
the current draft suggestions; it asks the LLM to refine the list and
returns a fresh ``list[Suggestion]`` ready to drop back into the UI.

Failures raise :class:`caseguide.llm.client.LLMError` (or a subclass);
the controller turns those into friendly UI messages and falls back
to the deterministic output when the LLM is unreachable.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from caseguide.llm.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_response,
)
from caseguide.model import Suggestion

if TYPE_CHECKING:
    from caseguide.case_reader import CaseScope
    from caseguide.llm.client import ChatClient

logger = logging.getLogger(__name__)


class SuggestionsRefiner:
    """Run a single refinement turn against the configured LLM."""

    def __init__(self, *, client: ChatClient) -> None:
        self._client = client

    def refine(
        self,
        *,
        scope: CaseScope,
        drafts: list[Suggestion],
    ) -> list[Suggestion]:
        """Return the LLM-refined suggestion list for ``scope``.

        Preserves the input draft list when the LLM produces something
        unusable (the caller already has the drafts on hand and
        re-running with a fresh model is cheap).
        """
        if not drafts:
            return []
        user_prompt = build_user_prompt(scope=scope, drafts=drafts)
        raw = self._client.chat(system=SYSTEM_PROMPT, user=user_prompt)
        refined = parse_response(raw)

        # Preserve the depends_on graph by mapping refined suggestions
        # back to draft ids when possible. The model should emit
        # ``source_id`` for entries it kept; we use it to retain the
        # original id (so completion tracking, when it lands, remains
        # stable across regenerations). Genuinely-new suggestions get
        # a "manual-N" id passed through verbatim.
        out: list[Suggestion] = []
        for index, item in enumerate(refined):
            kept_id = item.source_id or item.id
            if not kept_id:
                kept_id = f"refined-{index + 1}"
            out.append(
                Suggestion(
                    id=kept_id,
                    action=item.action,
                    priority=item.priority,
                    category=item.category,
                    expected_result=item.expected_result,
                    rationale=item.rationale,
                    references=list(item.references),
                    depends_on=list(item.depends_on),
                )
            )
        logger.info(
            "Refined %d draft suggestion(s) into %d via LLM", len(drafts), len(out)
        )
        return out


def annotate_with_source(suggestion: Suggestion, *, source_id: str) -> Suggestion:
    """Helper for callers that need to round-trip the source id field."""
    # Currently unused; kept for the eventual completion-tracking layer.
    return replace(suggestion, id=source_id)
