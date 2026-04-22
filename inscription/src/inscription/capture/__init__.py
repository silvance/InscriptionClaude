"""Capture engine: producer/consumer pipeline for screen capture events.

The engine is deliberately source-agnostic and sink-agnostic so Phase 4's
rolling-buffer source and Phase 2's annotation sinks can plug in without
changing the engine contract.

Layout:

- :class:`CaptureRequest` — the event flowing through the engine.
- :class:`CaptureResult` — produced after capture, fanned out to sinks.
- :class:`CaptureEngine` — orchestrator; owns a worker thread.
- :class:`CaptureSource` — abstract producer (hotkey, timer, manual).
- :class:`CaptureSink` — abstract consumer (repository, buffer).
- :class:`HotkeySource` — Phase 1 source wrapping :class:`HotkeyManager`.
- :class:`CaseRepositorySink` — Phase 1 sink that persists to the active case.
"""

from inscription.capture.engine import (
    CaptureEngine,
    CaptureRequest,
    CaptureResult,
    CaptureSink,
    CaptureSource,
)
from inscription.capture.hotkey_source import HotkeySource
from inscription.capture.repository_sink import CaseRepositorySink

__all__ = [
    "CaptureEngine",
    "CaptureRequest",
    "CaptureResult",
    "CaptureSink",
    "CaptureSource",
    "CaseRepositorySink",
    "HotkeySource",
]
