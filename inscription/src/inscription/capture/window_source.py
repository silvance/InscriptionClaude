"""Foreground-window change capture source.

Polls the foreground inspector on a timer. Whenever the active window
(title + process) changes, submits a :data:`EventKind.WINDOW_FOCUS` event.
Polling is fine here — UIA window events require a per-process hook that
isn't worth the complexity for alpha, and a 250 ms poll is invisible to
users while still catching every practical transition.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from inscription.capture.engine import CaptureSource
from inscription.capture.events import RawCaptureEvent
from inscription.model import EventKind, utcnow

if TYPE_CHECKING:
    from inscription.capture.engine import CaptureEngine
    from inscription.platform import ForegroundInspector

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_S = 0.25


class WindowFocusSource(CaptureSource):
    """Polls foreground window and emits an event on transition."""

    def __init__(
        self,
        *,
        inspector: ForegroundInspector,
        interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        self._inspector = inspector
        self._interval = interval_s
        self._engine: CaptureEngine | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_key: tuple[str, str] | None = None

    def start(self, engine: CaptureEngine) -> None:
        self._engine = engine
        self._stop.clear()
        thread = threading.Thread(target=self._run, name="inscription-window-watch", daemon=True)
        thread.start()
        self._thread = thread

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2 * self._interval + 0.5)
            self._thread = None
        self._engine = None

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._tick()
            except Exception:
                logger.exception("Window-focus poll failed")

    def _tick(self) -> None:
        engine = self._engine
        if engine is None:
            return
        info = self._inspector.inspect()
        key = (info.window_title or "", info.process_name or "")
        if key == self._last_key:
            return
        previous = self._last_key
        self._last_key = key
        # Ignore the very first observation — it's the window that was
        # already active when recording started, not a transition.
        if previous is None:
            return
        engine.submit(
            RawCaptureEvent(
                kind=EventKind.WINDOW_FOCUS,
                occurred_at=utcnow(),
                text=info.window_title or None,
            )
        )
