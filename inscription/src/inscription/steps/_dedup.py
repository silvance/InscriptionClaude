"""Click/keypress/scroll dedup state machines for the step generators.

Both :class:`inscription.steps.generator.StepGenerator` (post-recording
batch pass) and :class:`inscription.steps.live.LiveStepGenerator`
(real-time, while the examiner records) collapse rapid repeat events
into a single step. Until this module they each kept their own copy of
the dedup state — same heuristic, two implementations that could drift.

Three independent dedup machines:

* :class:`ClickDedup` — repeat clicks on the same UIA element merge.
* :class:`KeyPressDedup` — repeated milestone keys (Backspace x9, Enter
  spam) merge into a single "Press X N times" step.
* :class:`ScrollDedup` — consecutive scrolls in the same window merge
  into one "Scrolled in X" step.

Each ``observe`` returns True when the next event should be merged into
the previous step, False when it starts a new one.
"""

from __future__ import annotations

from dataclasses import dataclass

from inscription.model import EventKind

#: Two clicks on the same resolved element within this gap collapse into one.
CLICK_DEDUP_WINDOW_S = 0.8

#: Window-focus events within this window of a subsequent click are assumed
#: to be caused by that click. Lives here so both generators agree on the
#: number; only the batch generator has the lookahead to actually use it.
WINDOW_FOCUS_COALESCE_S = 0.6

#: Repeated milestone-key presses (Backspace, Enter, Tab) within this gap
#: collapse into one "Press X N times" step. Generous enough that
#: rapid-fire deletion / repeated Tab to navigate forms still merges,
#: short enough that two distinct presses minutes apart stay separate.
KEY_PRESS_DEDUP_WINDOW_S = 5.0

#: Consecutive scroll events in the same window within this gap merge.
SCROLL_DEDUP_WINDOW_S = 2.0


ClickKey = tuple[int | None, str | None]
KeyPressKey = tuple[str | None, str | None]
ScrollKey = tuple[str | None, str | None]


@dataclass(slots=True)
class ClickDedup:
    """Tracks the last appended click so the next can decide merge vs append."""

    last_key: ClickKey | None = None
    last_ts: float | None = None

    def observe(self, *, kind: EventKind, key: ClickKey, ts: float) -> bool:
        """Decide whether this click should merge into the previous step.

        Returns True when the caller should extend the previous step's
        source events (and not create a new one); False when this is a
        fresh click. Either way the dedup state advances.

        Always returns False for non-click event kinds so callers can
        feed every event in without branching.
        """
        if kind not in {EventKind.CLICK, EventKind.DOUBLE_CLICK}:
            self.last_key = None
            self.last_ts = None
            return False
        merge = (
            self.last_key is not None
            and self.last_key == key
            and self.last_ts is not None
            and (ts - self.last_ts) < CLICK_DEDUP_WINDOW_S
        )
        if merge:
            # Bump the timestamp so a third rapid click still merges.
            self.last_ts = ts
            return True
        self.last_key = key
        self.last_ts = ts
        return False

    def reset(self) -> None:
        self.last_key = None
        self.last_ts = None


@dataclass(slots=True)
class KeyPressDedup:
    """Coalesces repeated milestone-key presses (Backspace x9 → one step)."""

    last_key: KeyPressKey | None = None
    last_ts: float | None = None
    count: int = 0

    def observe(
        self, *, kind: EventKind, key: KeyPressKey, ts: float
    ) -> tuple[bool, int]:
        """Decide whether this key press merges into the previous step.

        Returns ``(merge, count)``:
        - ``merge`` is True when the caller should extend the previous
          step's source events instead of creating a new one.
        - ``count`` is the running total of merged presses for the
          current run (1 for the first press of a given key/window).

        Resets state on any non-key event so a click between two
        keypresses correctly starts a fresh count on the next press.
        """
        if kind is not EventKind.KEY_PRESS:
            self.last_key = None
            self.last_ts = None
            self.count = 0
            return (False, 0)
        merge = (
            self.last_key is not None
            and self.last_key == key
            and self.last_ts is not None
            and (ts - self.last_ts) < KEY_PRESS_DEDUP_WINDOW_S
        )
        if merge:
            self.last_ts = ts
            self.count += 1
            return (True, self.count)
        self.last_key = key
        self.last_ts = ts
        self.count = 1
        return (False, 1)

    def reset(self) -> None:
        self.last_key = None
        self.last_ts = None
        self.count = 0


@dataclass(slots=True)
class ScrollDedup:
    """Coalesces consecutive scroll events in the same window."""

    last_key: ScrollKey | None = None
    last_ts: float | None = None
    count: int = 0

    def observe(
        self, *, kind: EventKind, key: ScrollKey, ts: float
    ) -> tuple[bool, int]:
        """Same shape as :meth:`KeyPressDedup.observe` but for scrolls."""
        if kind is not EventKind.SCROLL:
            self.last_key = None
            self.last_ts = None
            self.count = 0
            return (False, 0)
        merge = (
            self.last_key is not None
            and self.last_key == key
            and self.last_ts is not None
            and (ts - self.last_ts) < SCROLL_DEDUP_WINDOW_S
        )
        if merge:
            self.last_ts = ts
            self.count += 1
            return (True, self.count)
        self.last_key = key
        self.last_ts = ts
        self.count = 1
        return (False, 1)

    def reset(self) -> None:
        self.last_key = None
        self.last_ts = None
        self.count = 0

