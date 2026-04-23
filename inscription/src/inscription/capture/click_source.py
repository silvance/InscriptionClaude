"""Mouse click capture source (``pynput`` backed).

Listens for mouse button presses and submits :class:`RawCaptureEvent`
objects of kind :data:`EventKind.CLICK` to the engine. Double-clicks are
detected by :class:`ClickSource` itself — the engine doesn't do any
temporal correlation.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from inscription.capture.engine import CaptureSource
from inscription.capture.events import RawCaptureEvent
from inscription.model import EventKind, utcnow

try:
    from pynput import mouse as _pynput_mouse

    _PYNPUT_AVAILABLE = True
except Exception:
    _pynput_mouse = None
    _PYNPUT_AVAILABLE = False

if TYPE_CHECKING:
    from inscription.capture.engine import CaptureEngine

logger = logging.getLogger(__name__)

#: Two clicks at the same point within this window merge into DOUBLE_CLICK.
DOUBLE_CLICK_WINDOW_S = 0.4
#: Pixel radius for the double-click position match.
DOUBLE_CLICK_RADIUS_PX = 4


class ClickSource(CaptureSource):
    """Convert pynput mouse press events into :class:`RawCaptureEvent`."""

    def __init__(self) -> None:
        self._engine: CaptureEngine | None = None
        self._listener: Any = None
        self._lock = threading.Lock()
        self._last_click_ts: float = 0.0
        self._last_click_xy: tuple[int, int] | None = None
        self._last_click_button: str | None = None

    def start(self, engine: CaptureEngine) -> None:
        if not _PYNPUT_AVAILABLE:
            logger.warning("pynput.mouse unavailable; ClickSource will not fire")
            self._engine = engine
            return
        self._engine = engine
        listener = _pynput_mouse.Listener(on_click=self._on_click)
        listener.daemon = True
        listener.start()
        self._listener = listener

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as exc:
                logger.warning("Error stopping mouse listener: %s", exc)
            self._listener = None
        self._engine = None

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not pressed:
            return
        engine = self._engine
        if engine is None:
            return
        button_name = getattr(button, "name", str(button))

        now = time.monotonic()
        kind = EventKind.CLICK
        with self._lock:
            if (
                self._last_click_xy is not None
                and button_name == self._last_click_button
                and now - self._last_click_ts <= DOUBLE_CLICK_WINDOW_S
                and abs(x - self._last_click_xy[0]) <= DOUBLE_CLICK_RADIUS_PX
                and abs(y - self._last_click_xy[1]) <= DOUBLE_CLICK_RADIUS_PX
            ):
                kind = EventKind.DOUBLE_CLICK
                # Reset so a triple-click doesn't also count as double.
                self._last_click_ts = 0.0
                self._last_click_xy = None
                self._last_click_button = None
            else:
                self._last_click_ts = now
                self._last_click_xy = (x, y)
                self._last_click_button = button_name

        engine.submit(
            RawCaptureEvent(
                kind=kind,
                occurred_at=utcnow(),
                button=button_name,
                x=int(x),
                y=int(y),
            )
        )
