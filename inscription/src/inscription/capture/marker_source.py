"""User-triggered marker source.

A "marker" is a deliberate annotation the user drops while recording — it
forces a screenshot and gives step generation a strong hint that this
point matters. Two entry points:

- Bound to a global hotkey (via :class:`HotkeyManager`).
- Emitted programmatically by the UI (e.g. a toolbar button).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from inscription.capture.engine import CaptureSource
from inscription.capture.events import RawCaptureEvent
from inscription.model import EventKind, utcnow
from inscription.platform import HotkeyBinding

if TYPE_CHECKING:
    from inscription.capture.engine import CaptureEngine
    from inscription.platform import HotkeyManager

logger = logging.getLogger(__name__)

DEFAULT_MARKER_HOTKEY = "<ctrl>+<shift>+m"


class MarkerSource(CaptureSource):
    """Expose :meth:`fire` directly and bind an optional hotkey."""

    def __init__(
        self,
        *,
        hotkey_manager: HotkeyManager | None = None,
        sequence: str = DEFAULT_MARKER_HOTKEY,
    ) -> None:
        self._hotkeys = hotkey_manager
        self._sequence = sequence
        self._engine: CaptureEngine | None = None

    def start(self, engine: CaptureEngine) -> None:
        self._engine = engine
        if self._hotkeys is not None:
            self._hotkeys.register(
                HotkeyBinding(sequence=self._sequence, name="marker"),
                self.fire,
            )

    def stop(self) -> None:
        if self._hotkeys is not None:
            self._hotkeys.unregister_all()
        self._engine = None

    def fire(self, note: str = "") -> None:
        """Emit a marker event. Safe to call from any thread."""
        engine = self._engine
        if engine is None:
            logger.debug("Marker fired without an engine bound")
            return
        engine.submit(
            RawCaptureEvent(
                kind=EventKind.MARKER,
                occurred_at=utcnow(),
                text=note or None,
            )
        )
