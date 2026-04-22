"""Capture engine orchestration.

The engine runs a worker thread that pulls :class:`CaptureRequest` objects
off a queue, executes the capture (screen grab + foreground inspection),
and fans the resulting :class:`CaptureResult` out to all registered sinks.

Sources (hotkey, timer, manual) submit requests via :meth:`CaptureEngine.submit`;
they don't need to know anything about sinks. Sinks consume results; they
don't need to know anything about sources. This is the lever that keeps
Phase 4's rolling buffer additive rather than a rewrite.
"""

from __future__ import annotations

import logging
import queue
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from inscription.cases.models import StepKind, utcnow

if TYPE_CHECKING:
    from datetime import datetime

    from inscription.platform import (
        CapturedImage,
        ForegroundInfo,
        ForegroundInspector,
        ScreenCapturer,
    )

logger = logging.getLogger(__name__)

# Sentinel pushed onto the queue to shut the worker thread down cleanly.
_STOP_SENTINEL = object()


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureRequest:
    """A request to capture the current screen.

    Sources build these and call :meth:`CaptureEngine.submit`. Fields other
    than ``requested_at`` and ``kind`` are hints; sinks may ignore them.
    """

    kind: StepKind
    requested_at: datetime = field(default_factory=utcnow)
    monitor_index: int | None = None
    title_hint: str = ""
    note: str = ""
    #: Free-form metadata sources can attach for sink consumption.
    extras: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureResult:
    """The outcome of a successful capture.

    Sinks receive one of these per request. A failed capture is logged and
    dropped; the request is not re-sent to any sink.
    """

    request: CaptureRequest
    image: CapturedImage
    foreground: ForegroundInfo
    captured_at: datetime


class CaptureSource(ABC):
    """Something that produces :class:`CaptureRequest` objects.

    The engine owns no sources directly; sources are started and stopped
    by application controller code and they push to the engine via
    :meth:`CaptureEngine.submit`.
    """

    @abstractmethod
    def start(self, engine: CaptureEngine) -> None:
        """Begin producing requests, submitting them to ``engine``."""

    @abstractmethod
    def stop(self) -> None:
        """Stop producing requests. Safe to call multiple times."""


@runtime_checkable
class CaptureSink(Protocol):
    """Something that consumes :class:`CaptureResult` objects.

    A :class:`~typing.Protocol` rather than an abstract base class so Qt
    widgets (which have their own metaclass) can implement the sink
    contract without fighting metaclass resolution.
    """

    def handle(self, result: CaptureResult) -> None:
        """Consume one capture result.

        Called on the engine's worker thread. Sinks must be thread-safe
        relative to their own external callers (e.g. Qt UI updates should
        be marshalled back to the main thread by the sink).
        """
        ...


class CaptureEngine:
    """Thread-safe producer/consumer capture engine.

    The engine owns:

    - A bounded queue of :class:`CaptureRequest` objects.
    - A dedicated worker thread that drains the queue.
    - A platform :class:`ScreenCapturer` and :class:`ForegroundInspector`
      used from the worker thread.
    - A set of registered sinks, invoked sequentially per result.

    It does not own sources; they are registered but their lifecycle is
    the caller's responsibility.
    """

    def __init__(
        self,
        *,
        screen_capturer: ScreenCapturer,
        foreground_inspector: ForegroundInspector,
        queue_maxsize: int = 32,
    ) -> None:
        self._screen = screen_capturer
        self._foreground = foreground_inspector
        self._queue: queue.Queue[object] = queue.Queue(maxsize=queue_maxsize)
        self._sinks: list[CaptureSink] = []
        self._sources: list[CaptureSource] = []
        self._worker: threading.Thread | None = None
        self._stopping = threading.Event()
        self._lock = threading.Lock()

    # -------------------------------------------------------- sinks/sources

    def add_sink(self, sink: CaptureSink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def remove_sink(self, sink: CaptureSink) -> None:
        with self._lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    def add_source(self, source: CaptureSource) -> None:
        """Register and start a source."""
        with self._lock:
            self._sources.append(source)
        source.start(self)

    def stop_sources(self) -> None:
        """Stop all registered sources without shutting down the engine."""
        with self._lock:
            sources = list(self._sources)
            self._sources.clear()
        for src in sources:
            try:
                src.stop()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Error stopping source %r: %s", src, exc)

    # -------------------------------------------------------- lifecycle

    def start(self) -> None:
        """Start the worker thread. No-op if already running."""
        if self._worker is not None and self._worker.is_alive():
            return
        self._stopping.clear()
        self._worker = threading.Thread(target=self._run, name="inscription-capture", daemon=True)
        self._worker.start()
        logger.info("Capture engine started")

    def stop(self, *, timeout: float = 5.0) -> None:
        """Stop the engine, its sources, and wait for the worker to drain.

        Pending requests in the queue are processed before shutdown.
        """
        self.stop_sources()
        self._stopping.set()
        self._queue.put(_STOP_SENTINEL)
        if self._worker is not None:
            self._worker.join(timeout=timeout)
            self._worker = None
        try:
            self._screen.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error closing screen capturer: %s", exc)
        logger.info("Capture engine stopped")

    # -------------------------------------------------------- submission

    def submit(self, request: CaptureRequest) -> bool:
        """Enqueue a capture request. Returns False if the queue is full.

        Sources should treat False as "drop this request and log"; we
        explicitly don't block sources on a full queue to avoid deadlocks
        when a sink is slow.
        """
        if self._stopping.is_set():
            logger.debug("Rejecting submit: engine is stopping")
            return False
        try:
            self._queue.put_nowait(request)
        except queue.Full:
            logger.warning("Capture queue full; dropping request %r", request)
            return False
        return True

    # -------------------------------------------------------- internals

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP_SENTINEL:
                self._queue.task_done()
                break
            assert isinstance(item, CaptureRequest)
            try:
                self._execute(item)
            except Exception:
                logger.exception("Capture execution failed for %r", item)
            finally:
                self._queue.task_done()

    def _execute(self, request: CaptureRequest) -> None:
        image = self._screen.capture(monitor_index=request.monitor_index)
        foreground = self._foreground.inspect()
        result = CaptureResult(
            request=request,
            image=image,
            foreground=foreground,
            captured_at=utcnow(),
        )
        with self._lock:
            sinks = list(self._sinks)
        for sink in sinks:
            try:
                sink.handle(result)
            except Exception:
                logger.exception("Sink %r failed on result", sink)
