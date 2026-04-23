"""Capture event types flowing from sources into the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from inscription.model import EventKind, utcnow

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class RawCaptureEvent:
    """One event submitted by a source.

    The engine enriches these with a screenshot and (for clicks) a resolved
    UI element before handing off to the sink. Sources shouldn't attempt to
    resolve elements or capture screenshots themselves; that keeps sources
    cheap and their listener threads unblocked.
    """

    kind: EventKind
    occurred_at: datetime = field(default_factory=utcnow)
    button: str | None = None
    x: int | None = None
    y: int | None = None
    key: str | None = None
    text: str | None = None
    #: Hint to the engine about whether this event warrants a screenshot.
    #: Engine may override (e.g. drop redundant screenshots).
    want_screenshot: bool = True
