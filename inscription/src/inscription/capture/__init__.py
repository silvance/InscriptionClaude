"""Capture pipeline.

The engine (see :mod:`inscription.capture.engine`) coordinates one or more
:class:`CaptureSource` producers with one or more :class:`CaptureSink`
consumers. Sources emit :class:`RawCaptureEvent` objects (with screenshots
already attached on the source's thread); the engine enriches each with
foreground info and an optional UIA-resolved element, and delivers the
result as an :class:`EnrichedEvent`.
"""

from inscription.capture.click_source import ClickSource
from inscription.capture.engine import (
    CaptureEngine,
    CaptureSink,
    CaptureSource,
    EnrichedEvent,
)
from inscription.capture.events import RawCaptureEvent
from inscription.capture.keyboard_source import KeyboardMilestoneSource
from inscription.capture.scroll_source import ScrollSource
from inscription.capture.session_sink import SessionSink
from inscription.capture.window_source import WindowFocusSource

__all__ = [
    "CaptureEngine",
    "CaptureSink",
    "CaptureSource",
    "ClickSource",
    "EnrichedEvent",
    "KeyboardMilestoneSource",
    "RawCaptureEvent",
    "ScrollSource",
    "SessionSink",
    "WindowFocusSource",
]
