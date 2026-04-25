"""Click-dedup state machine shared by the batch and live step generators.

Both :class:`inscription.steps.generator.StepGenerator` (post-recording
batch pass) and :class:`inscription.steps.live.LiveStepGenerator`
(real-time, while the examiner records) collapse rapid repeat clicks
on the same UIA element into a single step. Until this module they
each kept their own copy of the dedup state — same heuristic, two
implementations that could drift.

The state is small: the (resolved-element-id, window-title) "click
key" of the last appended step plus its timestamp. ``observe`` returns
True when the next click should be merged into the previous step,
False when it starts a new one.
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


ClickKey = tuple[int | None, str | None]


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
