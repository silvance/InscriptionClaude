"""Live step generation while a recording is in progress.

The batch :class:`StepGenerator` runs after a recording finishes and
rewrites every step from scratch. That's a great final pass but leaves
the examiner looking at an empty notes panel for the duration of the
exam. This module fills that gap: a :class:`CaptureSink` that builds
draft steps incrementally as events stream in.

Strategy:

- Each new ``EnrichedEvent`` either *extends* the previous step (when
  it's a rapid duplicate click on the same UIA element) or *appends* a
  new step. There's no buffering / lookahead — events show up in the
  notes panel within ~50ms of happening.
- Window-focus events that look like side-effects of an upcoming click
  can't be filtered the way the batch generator filters them (the
  batch one peeks ahead). We accept the small extra noise here because
  the post-recording :class:`StepGenerator` runs anyway and cleans
  things up. Manual edits made mid-recording survive that pass because
  the batch generator preserves any step whose ``source_event_ids``
  matches an existing ``manual_edit`` row.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from inscription.model import DraftStep, RawEvent
from inscription.steps._dedup import ClickDedup
from inscription.steps.generator import render_step_action

if TYPE_CHECKING:
    from collections.abc import Callable

    from inscription.capture.engine import EnrichedEvent
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)


class LiveStepGenerator:
    """Capture sink that maintains the draft_steps table in real time.

    Construct one per recording and register it on the engine *after*
    the :class:`SessionSink` so the raw event has been persisted (and
    has an ``id``) by the time we run.

    ``on_changed`` is called from the capture worker thread after every
    successful append/extend; the controller bridges that to a Qt
    queued signal so the UI reloads on the GUI thread.
    """

    def __init__(
        self,
        repository: SessionRepository,
        *,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        self._repo = repository
        self._on_changed = on_changed
        self._lock = threading.Lock()
        # Track the last appended step's id so the dedup machine can
        # extend its source events when the next click merges in.
        self._last_step_id: int | None = None
        self._dedup = ClickDedup()

    # ------------------------------------------------------------ sink API

    def handle(self, event: EnrichedEvent) -> None:
        # SessionSink runs first and stamps the persisted id onto the
        # event. If it's still None something went wrong upstream and
        # there's nothing for the step to reference.
        if event.persisted_event_id is None:
            return

        with self._lock:
            self._handle_locked(event=event, raw_id=event.persisted_event_id)

        if self._on_changed is not None:
            try:
                self._on_changed()
            except Exception:
                logger.exception("LiveStepGenerator on_changed callback failed")

    # --------------------------------------------------------- internals

    def _handle_locked(self, *, event: EnrichedEvent, raw_id: int) -> None:
        raw = event.raw
        element_id = event.resolved.id if event.resolved is not None else None
        should_merge = self._dedup.observe(
            kind=raw.kind,
            key=(element_id, event.foreground.window_title),
            ts=raw.occurred_at.timestamp(),
        )
        if should_merge and self._last_step_id is not None:
            self._repo.extend_step_sources(
                self._last_step_id,
                extra_event_ids=(raw_id,),
                screenshot_id=event.persisted_screenshot_id,
            )
            return

        action_text = render_step_action(
            self._adapt(raw_id=raw_id, event=event),
            event.resolved,
        )
        step = self._repo.append_step(
            DraftStep(
                id=None,
                sequence=0,  # assigned by append_step
                action=action_text,
                source_event_ids=(raw_id,),
                screenshot_id=event.persisted_screenshot_id,
            )
        )
        self._last_step_id = step.id

    @staticmethod
    def _adapt(*, raw_id: int, event: EnrichedEvent) -> RawEvent:
        """Adapt the in-flight event to the :class:`RawEvent` render helpers.

        ``render_step_action`` was written against the persisted RawEvent
        shape; reusing it keeps the live and batch wording identical.
        """
        raw = event.raw
        fg = event.foreground
        return RawEvent(
            id=raw_id,
            sequence=0,
            occurred_at=raw.occurred_at,
            kind=raw.kind,
            button=raw.button,
            x=raw.x,
            y=raw.y,
            key=raw.key,
            text=raw.text,
            window_title=fg.window_title or None,
            process_name=fg.process_name or None,
            screenshot_id=None,
            resolved_element_id=event.resolved.id if event.resolved else None,
        )
