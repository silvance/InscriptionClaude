"""Capture pipeline.

The engine (see :mod:`inscription.capture.engine`) coordinates one or more
:class:`CaptureSource` producers with one or more :class:`CaptureSink`
consumers. Sources emit :class:`RawCaptureEvent` objects; the engine
enriches each with a screenshot, foreground info, and optional UIA-
resolved element, and delivers the result as an :class:`EnrichedEvent`.
"""

from inscription.capture.click_source import ClickSource
from inscription.capture.engine import (
    CaptureEngine,
    CaptureSink,
    CaptureSource,
    EngineStats,
    EnrichedEvent,
)
from inscription.capture.events import RawCaptureEvent
from inscription.capture.keyboard_source import KeyboardMilestoneSource
from inscription.capture.marker_source import MarkerSource
from inscription.capture.session_sink import SessionSink
from inscription.capture.window_source import WindowFocusSource

__all__ = [
    "CaptureEngine",
    "CaptureSink",
    "CaptureSource",
    "ClickSource",
    "EngineStats",
    "EnrichedEvent",
    "KeyboardMilestoneSource",
    "MarkerSource",
    "RawCaptureEvent",
    "SessionSink",
    "WindowFocusSource",
]
