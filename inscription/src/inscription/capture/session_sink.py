"""Sink that persists enriched events into a :class:`SessionRepository`.

The sink writes the PNG to disk, inserts a ``screenshot_artifacts`` row,
inserts a ``resolved_elements`` row (when a click resolved something), and
finally inserts the ``raw_events`` row that references them.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inscription.capture.engine import EnrichedEvent
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)


def _filename_for(event_seq: int) -> str:
    return f"event-{event_seq:06d}.png"


class SessionSink:
    """Persists captures to a live :class:`SessionRepository`.

    Implements the :class:`inscription.capture.engine.CaptureSink` protocol
    by duck-typing — it provides a ``handle`` method with the right signature.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository
        self._lock = threading.Lock()
        # Seed from existing state so a second recording on the same session
        # doesn't collide with filenames from the first one. The screenshots
        # table has a UNIQUE constraint on relative_path.
        self._counter = len(repository.list_screenshots())

    def handle(self, event: EnrichedEvent) -> None:
        raw = event.raw
        with self._lock:
            self._counter += 1
            counter = self._counter

        screenshot_id: int | None = None
        if raw.png_bytes:
            relative = f"screenshots/{_filename_for(counter)}"
            target = self._repo.session.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw.png_bytes)
            artifact = self._repo.add_screenshot(
                relative_path=relative,
                captured_at=event.processed_at,
                width=raw.png_width,
                height=raw.png_height,
                sha256=event.image_sha256,
            )
            screenshot_id = artifact.id

        resolved_id: int | None = None
        if event.resolved is not None and event.resolved.confidence > 0:
            stored = self._repo.add_resolved_element(event.resolved)
            resolved_id = stored.id

        self._repo.append_event(
            kind=raw.kind,
            occurred_at=raw.occurred_at,
            button=raw.button,
            x=raw.x,
            y=raw.y,
            key=raw.key,
            text=raw.text,
            window_title=event.foreground.window_title or None,
            process_name=event.foreground.process_name or None,
            screenshot_id=screenshot_id,
            resolved_element_id=resolved_id,
        )
        logger.debug(
            "Persisted %s event (screenshot=%s, resolved=%s)",
            raw.kind.value,
            screenshot_id,
            resolved_id,
        )
