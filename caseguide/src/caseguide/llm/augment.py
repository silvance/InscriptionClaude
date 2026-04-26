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

        Completed entries are deliberately held back from the LLM and
        merged into the result unchanged: once an examiner has marked
        a step done we don't want a refine pass to overwrite the
        action text or drop the entry, since the work has already
        been performed against that exact wording.
        """
        if not drafts:
            return []
        active_drafts = [d for d in drafts if not d.completed]
        completed = [d for d in drafts if d.completed]
        if not active_drafts:
            # Nothing to refine — every entry is already done. Return
            # the completed entries verbatim so callers don't see an
            # empty list (which they treat as "LLM failed").
            return list(completed)
        user_prompt = build_user_prompt(scope=scope, drafts=active_drafts)
        raw = self._client.chat(system=SYSTEM_PROMPT, user=user_prompt)
        refined = parse_response(raw)

        # Preserve the depends_on graph by mapping refined suggestions
        # back to draft ids when possible. The model should emit
        # ``source_id`` for entries it kept; we use it to retain the
        # original id so completion tracking remains stable across
        # regenerations. Genuinely-new suggestions get a "manual-N" id
        # passed through verbatim.
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
        # Sort completed entries to the bottom so the list reads as
        # "what's left" first, "what's done" after.
        out.extend(completed)
        logger.info(
            "Refined %d active draft(s) into %d via LLM (preserved %d completed)",
            len(active_drafts),
            len(out) - len(completed),
            len(completed),
        )
        return out
