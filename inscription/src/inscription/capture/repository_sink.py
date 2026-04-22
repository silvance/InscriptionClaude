"""Case-repository capture sink.

The sink writes each :class:`CaptureResult` to disk (PNG) and appends a
step row to the active case's database. Invoked from the engine worker
thread; we keep the repository handle fixed for the lifetime of the sink
(one sink per open case).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from inscription.capture.engine import CaptureSink

if TYPE_CHECKING:
    from inscription.capture.engine import CaptureResult
    from inscription.storage import CaseRepository

logger = logging.getLogger(__name__)


def _filename_for(result: CaptureResult, sequence: int) -> str:
    """Build a stable, sortable filename for a capture's screenshot."""
    ts = result.captured_at.strftime("%Y-%m-%dT%H-%M-%S")
    return f"{ts}-{sequence:05d}.png"


class CaseRepositorySink(CaptureSink):
    """Persists captures to an active :class:`CaseRepository`.

    The sink tracks a single active session ID — when the controller opens
    a case, it calls :meth:`set_session`; when the case closes, the sink
    is removed from the engine and discarded. Multiple sessions per case
    is a Phase 4 concern.
    """

    def __init__(self, repository: CaseRepository) -> None:
        self._repo = repository
        self._session_id: int | None = None
        self._sequence = 0
        self._lock = threading.Lock()

    def set_session(self, session_id: int) -> None:
        """Bind subsequent captures to ``session_id``."""
        with self._lock:
            self._session_id = session_id
            self._sequence = 0

    def handle(self, result: CaptureResult) -> None:
        with self._lock:
            if self._session_id is None:
                logger.warning("Capture dropped: no active session on sink")
                return
            session_id = self._session_id
            self._sequence += 1
            sequence = self._sequence

        case = self._repo.case
        filename = _filename_for(result, sequence)
        target = case.screenshots_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.image.png_bytes)

        relative = f"screenshots/{filename}"
        title = result.request.title_hint or _title_from_foreground(result)
        self._repo.append_step(
            session_id=session_id,
            kind=result.request.kind,
            title=title,
            body_markdown=result.request.note,
            screenshot_path=relative,
            captured_at=result.captured_at,
        )
        logger.debug(
            "Persisted capture seq=%d kind=%s -> %s",
            sequence,
            result.request.kind,
            relative,
        )


def _title_from_foreground(result: CaptureResult) -> str:
    """Fallback title derived from foreground context."""
    fg = result.foreground
    if fg.window_title:
        return fg.window_title
    if fg.process_name:
        return fg.process_name
    return "Capture"
