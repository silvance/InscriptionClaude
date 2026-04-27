"""Session → LLM → rewritten draft_steps orchestration.

The rewriter is intentionally a thin sequence: read events and elements
from the repository, ask :class:`LLMClient` to rewrite, parse the
response, and write back via :meth:`SessionRepository.replace_steps`.

Manual-edit preservation mirrors the rule-based :class:`StepGenerator`:
a step whose ``source_event_ids`` match an existing ``manual_edit`` row
is copied verbatim rather than overwritten with the LLM's text.

A pre-pass also handles the empty-session case: if there are no events
yet, there is nothing to rewrite — we don't call the LLM at all.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from suite_common.llm import LLMResponseError

from inscription.llm.prompt import SYSTEM_PROMPT, build_user_prompt, parse_response
from inscription.model import DraftStep

if TYPE_CHECKING:
    from suite_common.llm import ChatClient

    from inscription.llm.prompt import RewrittenStep
    from inscription.model import RawEvent, ResolvedElement
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)


class StepRewriter:
    """Rewrite a session's draft_steps using a language model."""

    def __init__(self, *, repository: SessionRepository, client: ChatClient) -> None:
        self._repo = repository
        self._client = client

    def rewrite(self) -> list[DraftStep]:
        """Rewrite in-place. Returns the persisted :class:`DraftStep` list.

        Raises :class:`inscription.llm.LLMError` subclasses on any failure;
        the caller is expected to catch and fall back to the rule-based
        text (which remains intact in the DB because we only write on
        success).
        """
        events = self._repo.list_events()
        if not events:
            logger.info("rewrite: session has no events, nothing to do")
            return self._repo.list_steps()

        existing_steps = self._repo.list_steps(include_suppressed=True)
        manual_by_sources: dict[tuple[int, ...], DraftStep] = {
            s.source_event_ids: s for s in existing_steps if s.manual_edit
        }

        resolved_by_id = self._load_resolved_elements(events)

        user_prompt = build_user_prompt(
            session_name=self._repo.session.info.name,
            events=events,
            resolved_by_id=resolved_by_id,
            existing_steps=existing_steps,
        )

        raw = self._client.chat(system=SYSTEM_PROMPT, user=user_prompt)
        valid_ids = {e.id for e in events if e.id is not None}
        rewritten = parse_response(raw, valid_event_ids=valid_ids)

        new_steps = self._materialise(
            rewritten=rewritten,
            events=events,
            manual_by_sources=manual_by_sources,
        )
        if not new_steps:
            msg = "LLM produced no usable steps after manual-edit merge"
            raise LLMResponseError(msg)

        saved = self._repo.replace_steps(new_steps)
        self._repo.flush_manifest()
        logger.info(
            "rewrite: %d events → %d steps (from %d proposed)",
            len(events),
            len(saved),
            len(rewritten),
        )
        return saved

    # ---------------------------------------------------------- internals

    def _load_resolved_elements(self, events: list[RawEvent]) -> dict[int, ResolvedElement]:
        ids = {e.resolved_element_id for e in events if e.resolved_element_id is not None}
        out: dict[int, ResolvedElement] = {}
        for element_id in ids:
            elem = self._repo.get_resolved_element(element_id)
            if elem is not None:
                out[element_id] = elem
        return out

    @staticmethod
    def _materialise(
        *,
        rewritten: list[RewrittenStep],
        events: list[RawEvent],
        manual_by_sources: dict[tuple[int, ...], DraftStep],
    ) -> list[DraftStep]:
        """Turn parsed LLM steps into DraftStep rows ready for replace_steps.

        Picks each step's screenshot_id from the last referenced event that
        has one (the "result of the action" frame is usually most useful).
        Preserves manual-edit text when the key matches.
        """
        events_by_id = {e.id: e for e in events if e.id is not None}
        out: list[DraftStep] = []
        for item in rewritten:
            screenshot_id = _pick_screenshot_id(item.source_event_ids, events_by_id)
            preserved = manual_by_sources.get(item.source_event_ids)
            if preserved is not None:
                action = preserved.action
                result = preserved.result
            else:
                action = item.action
                result = item.result
            out.append(
                DraftStep(
                    id=None,
                    sequence=0,  # assigned by replace_steps
                    action=action,
                    result=result,
                    source_event_ids=item.source_event_ids,
                    screenshot_id=screenshot_id,
                    manual_edit=preserved is not None,
                )
            )
        return out


def _pick_screenshot_id(
    source_event_ids: tuple[int, ...], events_by_id: dict[int, RawEvent]
) -> int | None:
    for eid in reversed(source_event_ids):
        event = events_by_id.get(eid)
        if event is not None and event.screenshot_id is not None:
            return event.screenshot_id
    return None
