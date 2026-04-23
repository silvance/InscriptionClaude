"""Keyboard milestone capture source.

We deliberately do **not** capture every keystroke. Doing so would:

- Produce unreadable draft steps ("Press A, Press s, Press d, Press f…")
- Risk capturing sensitive text (passwords, private notes) into a
  shareable guide.

Instead we capture "milestones" — keys that usually mark a meaningful
transition in a workflow: ``Enter``, ``Tab``, ``Escape``, and the function
keys. Step generation can combine a milestone with the preceding click to
produce text like "Type the URL and press Enter".
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from inscription.capture.engine import CaptureSource
from inscription.capture.events import RawCaptureEvent
from inscription.model import EventKind, utcnow

try:
    from pynput import keyboard as _pynput_keyboard

    _PYNPUT_AVAILABLE = True
except Exception:
    _pynput_keyboard = None
    _PYNPUT_AVAILABLE = False

if TYPE_CHECKING:
    from inscription.capture.engine import CaptureEngine

logger = logging.getLogger(__name__)

#: The named keys we report as milestones. Everything else is ignored.
MILESTONE_KEYS: frozenset[str] = frozenset(
    {
        "enter",
        "tab",
        "esc",
        "backspace",
        "delete",
        "f1",
        "f2",
        "f3",
        "f4",
        "f5",
        "f6",
        "f7",
        "f8",
        "f9",
        "f10",
        "f11",
        "f12",
    }
)


class KeyboardMilestoneSource(CaptureSource):
    """Emit KEY_PRESS events for milestone keys only."""

    def __init__(self, milestones: frozenset[str] = MILESTONE_KEYS) -> None:
        self._milestones = {k.lower() for k in milestones}
        self._engine: CaptureEngine | None = None
        self._listener: Any = None

    def start(self, engine: CaptureEngine) -> None:
        if not _PYNPUT_AVAILABLE:
            logger.warning("pynput.keyboard unavailable; KeyboardMilestoneSource will not fire")
            self._engine = engine
            return
        self._engine = engine
        listener = _pynput_keyboard.Listener(on_press=self._on_press)
        listener.daemon = True
        listener.start()
        self._listener = listener

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as exc:
                logger.warning("Error stopping keyboard listener: %s", exc)
            self._listener = None
        self._engine = None

    def _on_press(self, key: Any) -> None:
        engine = self._engine
        if engine is None:
            return
        name = _key_name(key)
        if name is None or name.lower() not in self._milestones:
            return
        engine.submit(
            RawCaptureEvent(
                kind=EventKind.KEY_PRESS,
                occurred_at=utcnow(),
                key=name,
                want_screenshot=False,
            )
        )


def _key_name(key: Any) -> str | None:
    """Return the name of a pynput special key, or None for ordinary chars."""
    # pynput exposes named keys as Key.enter, Key.tab, ... with a ``name`` attr.
    name = getattr(key, "name", None)
    if isinstance(name, str):
        return name
    return None
