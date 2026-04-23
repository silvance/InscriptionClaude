"""Capture engine orchestration.

The engine runs a worker thread that pulls :class:`RawCaptureEvent` objects
off a queue, enriches them (screenshot + foreground inspection + optional
UIA resolution), and fans the result out to registered sinks.

Sources (click, keyboard, window-focus) submit events via
:meth:`CaptureEngine.submit`; they don't need to know about sinks. Sinks
consume enriched events; they don't need to know about sources.

Platform objects (``ScreenCapturer``, ``ForegroundInspector``,
``ElementResolver``) are constructed inside the worker thread via factory
callables because ``mss`` and UIA are not thread-safe.
"""

from __future__ import annotations

import hashlib
import logging
import queue
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from inscription.capture.events import RawCaptureEvent
from inscription.model import EventKind, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from inscription.model import ResolvedElement
    from inscription.platform import (
        CapturedImage,
        ForegroundInfo,
        ForegroundInspector,
        ScreenCapturer,
    )
    from inscription.resolve import ElementResolver

logger = logging.getLogger(__name__)

_STOP_SENTINEL = object()


@dataclass(frozen=True, slots=True, kw_only=True)
class EnrichedEvent:
    """A raw event plus everything the sink needs to persist it."""

    raw: RawCaptureEvent
    processed_at: datetime
    foreground: ForegroundInfo
    image: CapturedImage | None = None
    image_sha256: str = ""
    resolved: ResolvedElement | None = None


class CaptureSource(ABC):
    """A producer of :class:`RawCaptureEvent` objects."""

    @abstractmethod
    def start(self, engine: CaptureEngine) -> None:
        """Begin producing events, submitting them to ``engine``."""

    @abstractmethod
    def stop(self) -> None:
        """Stop producing events. Safe to call multiple times."""


@runtime_checkable
class CaptureSink(Protocol):
    """Consumes :class:`EnrichedEvent` objects."""

    def handle(self, event: EnrichedEvent) -> None:  # pragma: no cover - protocol
        ...


@dataclass
class EngineStats:
    """Diagnostic counters. Inspected by tests and the status bar."""

    submitted: int = 0
    processed: int = 0
    dropped_queue_full: int = 0
    screenshot_errors: int = 0
    resolver_errors: int = 0
    sink_errors: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class CaptureEngine:
    """Thread-safe producer/consumer capture engine.

    The engine owns:

    - A bounded queue of :class:`RawCaptureEvent` objects.
    - A dedicated worker thread that drains the queue.
    - Platform objects (screen, foreground inspector, resolver) constructed
      inside the worker thread via factories.
    - A set of registered sinks invoked sequentially per event.
    """

    def __init__(
        self,
        *,
        screen_factory: Callable[[], ScreenCapturer],
        foreground_factory: Callable[[], ForegroundInspector],
        resolver_factory: Callable[[ForegroundInspector], ElementResolver],
        queue_maxsize: int = 256,
    ) -> None:
        self._screen_factory = screen_factory
        self._foreground_factory = foreground_factory
        self._resolver_factory = resolver_factory
        self._queue: queue.Queue[object] = queue.Queue(maxsize=queue_maxsize)
        self._sinks: list[CaptureSink] = []
        self._sources: list[CaptureSource] = []
        self._worker: threading.Thread | None = None
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        self.stats = EngineStats()

    # -------------------------------------------------------- sinks/sources

    def add_sink(self, sink: CaptureSink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def remove_sink(self, sink: CaptureSink) -> None:
        with self._lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    def add_source(self, source: CaptureSource) -> None:
        with self._lock:
            self._sources.append(source)
        source.start(self)

    def stop_sources(self) -> None:
        with self._lock:
            sources = list(self._sources)
            self._sources.clear()
        for src in sources:
            try:
                src.stop()
            except Exception as exc:
                logger.warning("Error stopping source %r: %s", src, exc)

    # -------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._stopping.clear()
        self._worker = threading.Thread(target=self._run, name="inscription-capture", daemon=True)
        self._worker.start()
        logger.info("Capture engine started")

    def stop(self, *, timeout: float = 5.0) -> None:
        self.stop_sources()
        self._stopping.set()
        self._queue.put(_STOP_SENTINEL)
        if self._worker is not None:
            self._worker.join(timeout=timeout)
            self._worker = None
        logger.info("Capture engine stopped")

    # -------------------------------------------------------- submission

    def submit(self, event: RawCaptureEvent) -> bool:
        """Enqueue a raw event. Returns False if the queue is full."""
        if self._stopping.is_set():
            return False
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            with self.stats._lock:
                self.stats.dropped_queue_full += 1
            logger.warning("Capture queue full; dropping %r", event.kind)
            return False
        with self.stats._lock:
            self.stats.submitted += 1
        return True

    # -------------------------------------------------------- internals

    def _run(self) -> None:
        # Create platform objects on this thread — mss/UIA aren't thread-safe.
        try:
            screen = self._screen_factory()
            foreground = self._foreground_factory()
            resolver = self._resolver_factory(foreground)
        except Exception:
            logger.exception("Failed to initialise capture platform")
            return

        try:
            while True:
                item = self._queue.get()
                if item is _STOP_SENTINEL:
                    self._queue.task_done()
                    break
                assert isinstance(item, RawCaptureEvent)
                try:
                    self._process(item, screen=screen, foreground=foreground, resolver=resolver)
                except Exception:
                    logger.exception("Processing failed for %r", item)
                finally:
                    self._queue.task_done()
        finally:
            try:
                screen.close()
            except Exception as exc:
                logger.warning("Error closing screen capturer: %s", exc)

    def _process(
        self,
        raw: RawCaptureEvent,
        *,
        screen: ScreenCapturer,
        foreground: ForegroundInspector,
        resolver: ElementResolver,
    ) -> None:

        image: CapturedImage | None = None
        sha = ""
        if raw.want_screenshot:
            try:
                image = screen.capture()
                sha = hashlib.sha256(image.png_bytes).hexdigest()
            except Exception:
                logger.exception("Screenshot failed for %r", raw.kind)
                with self.stats._lock:
                    self.stats.screenshot_errors += 1

        fg = foreground.inspect()

        resolved = None
        is_click = raw.kind in {EventKind.CLICK, EventKind.DOUBLE_CLICK}
        if is_click and raw.x is not None and raw.y is not None:
            try:
                resolved = resolver.resolve_at(raw.x, raw.y)
            except Exception:
                logger.exception("Resolver failed at (%s,%s)", raw.x, raw.y)
                with self.stats._lock:
                    self.stats.resolver_errors += 1

        enriched = EnrichedEvent(
            raw=raw,
            processed_at=utcnow(),
            foreground=fg,
            image=image,
            image_sha256=sha,
            resolved=resolved,
        )

        with self._lock:
            sinks = list(self._sinks)
        for sink in sinks:
            try:
                sink.handle(enriched)
            except Exception:
                logger.exception("Sink %r failed", sink)
                with self.stats._lock:
                    self.stats.sink_errors += 1

        with self.stats._lock:
            self.stats.processed += 1
