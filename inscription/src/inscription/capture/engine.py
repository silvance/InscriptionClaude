"""Capture engine orchestration.

The engine runs a worker thread that pulls :class:`RawCaptureEvent` objects
off a queue, enriches them with foreground info and (for clicks) a resolved
UI element, and fans the result out to registered sinks.

Screenshots are captured on the source's own thread (``mss`` is not
thread-safe) and attached to the raw event, not taken here. See
:mod:`inscription.capture.events`.

Sources (click, keyboard, window-focus) submit events via
:meth:`CaptureEngine.submit`; they don't need to know about sinks. Sinks
consume enriched events; they don't need to know about sources.

``ForegroundInspector`` and ``ElementResolver`` are constructed inside
the worker thread via factory callables because UIA isn't thread-safe.
"""

from __future__ import annotations

import hashlib
import logging
import os
import queue
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from inscription.capture.events import RawCaptureEvent
from inscription.model import EventKind, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from inscription.model import ResolvedElement
    from inscription.platform import ForegroundInfo, ForegroundInspector
    from inscription.resolve import ElementResolver

logger = logging.getLogger(__name__)

_STOP_SENTINEL = object()


@dataclass(slots=True, kw_only=True)
class EnrichedEvent:
    """A raw event plus everything the sink needs to persist it.

    Sinks run sequentially in registration order; ``SessionSink`` writes
    the persisted ``raw_events.id`` and ``screenshot_artifacts.id`` onto
    these mutable fields so downstream sinks (e.g.
    :class:`inscription.steps.live.LiveStepGenerator`) can reference the
    just-saved row without re-querying.
    """

    raw: RawCaptureEvent
    processed_at: datetime
    foreground: ForegroundInfo
    image_sha256: str = ""
    resolved: ResolvedElement | None = None
    persisted_event_id: int | None = None
    persisted_screenshot_id: int | None = None
    persisted_resolved_id: int | None = None


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


class CaptureEngine:
    """Thread-safe producer/consumer capture engine."""

    def __init__(
        self,
        *,
        foreground_factory: Callable[[], ForegroundInspector],
        resolver_factory: Callable[[ForegroundInspector], ElementResolver],
        queue_maxsize: int = 256,
        own_pid: int | None = None,
    ) -> None:
        self._foreground_factory = foreground_factory
        self._resolver_factory = resolver_factory
        self._queue: queue.Queue[object] = queue.Queue(maxsize=queue_maxsize)
        self._sinks: list[CaptureSink] = []
        self._sources: list[CaptureSource] = []
        self._worker: threading.Thread | None = None
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        # Inscription's own pid. Events whose foreground process matches
        # this are dropped silently — examiners frequently click back into
        # Inscription mid-recording to read the live notes or tweak a
        # step, and those clicks are noise, not part of the workflow.
        # Markers are explicitly exempt because they are user-intent.
        self._own_pid = own_pid if own_pid is not None else os.getpid()

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
        """Enqueue a raw event. Returns False if the queue is full or the
        engine is shutting down."""
        if self._stopping.is_set():
            return False
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            logger.warning("Capture queue full; dropping %r", event.kind)
            return False
        return True

    # -------------------------------------------------------- internals

    def _run(self) -> None:
        try:
            foreground = self._foreground_factory()
            resolver = self._resolver_factory(foreground)
        except Exception:
            logger.exception("Failed to initialise capture platform")
            return

        while True:
            item = self._queue.get()
            if item is _STOP_SENTINEL:
                self._queue.task_done()
                break
            assert isinstance(item, RawCaptureEvent)
            try:
                self._process(item, foreground=foreground, resolver=resolver)
            except Exception:
                logger.exception("Processing failed for %r", item)
            finally:
                self._queue.task_done()

    def _process(
        self,
        raw: RawCaptureEvent,
        *,
        foreground: ForegroundInspector,
        resolver: ElementResolver,
    ) -> None:
        fg = foreground.inspect()

        # Drop everything except markers when the foreground belongs to
        # Inscription itself. The examiner is interacting with the
        # recorder window, not the workflow under examination. Markers
        # come straight from the controller as a deliberate signal, so
        # let those through regardless.
        if (
            raw.kind is not EventKind.MARKER
            and fg.process_id is not None
            and fg.process_id == self._own_pid
        ):
            logger.debug("Dropping self-event (pid=%s, kind=%s)", fg.process_id, raw.kind)
            return

        sha = hashlib.sha256(raw.png_bytes).hexdigest() if raw.png_bytes else ""

        resolved = None
        is_click = raw.kind in {EventKind.CLICK, EventKind.DOUBLE_CLICK}
        if is_click and raw.x is not None and raw.y is not None:
            try:
                resolved = resolver.resolve_at(raw.x, raw.y)
            except Exception:
                logger.exception("Resolver failed at (%s,%s)", raw.x, raw.y)

        enriched = EnrichedEvent(
            raw=raw,
            processed_at=utcnow(),
            foreground=fg,
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
