"""Capture engine: end-to-end with a fake foreground/resolver."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from inscription.capture import (
    CaptureEngine,
    EnrichedEvent,
    RawCaptureEvent,
)
from inscription.model import EventKind, ResolvedElement
from inscription.platform import (
    ForegroundInfo,
    ForegroundInspector,
)
from inscription.resolve import ElementResolver

if TYPE_CHECKING:
    from collections.abc import Callable


class _CollectingSink:
    def __init__(self) -> None:
        self.events: list[EnrichedEvent] = []
        self._lock = threading.Lock()

    def handle(self, event: EnrichedEvent) -> None:
        with self._lock:
            self.events.append(event)


class _FakeForeground(ForegroundInspector):
    def inspect(self) -> ForegroundInfo:
        return ForegroundInfo(
            window_title="FakeApp",
            process_name="fake.exe",
            process_id=999,
        )


class _FakeResolver(ElementResolver):
    def resolve_at(self, x: int, y: int) -> ResolvedElement:
        return ResolvedElement(
            id=None,
            name=f"control-at-{x}-{y}",
            control_type="Button",
            confidence=0.9,
            method="uia",
        )


def _wait_for(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("predicate never became true")


def _fake_resolver(_inspector: ForegroundInspector) -> ElementResolver:
    return _FakeResolver()


def test_engine_enriches_click_with_screenshot_and_resolver() -> None:
    engine = CaptureEngine(
        foreground_factory=_FakeForeground,
        resolver_factory=_fake_resolver,
    )
    sink = _CollectingSink()
    engine.add_sink(sink)
    engine.start()
    try:
        engine.submit(
            RawCaptureEvent(
                kind=EventKind.CLICK,
                x=42,
                y=13,
                button="left",
                png_bytes=b"\x89PNG-fake",
                png_width=8,
                png_height=8,
            )
        )
        _wait_for(lambda: len(sink.events) == 1)
    finally:
        engine.stop()

    assert len(sink.events) == 1
    enriched = sink.events[0]
    assert enriched.raw.kind is EventKind.CLICK
    assert enriched.raw.png_bytes == b"\x89PNG-fake"
    assert enriched.image_sha256
    assert enriched.resolved is not None
    assert enriched.resolved.name == "control-at-42-13"
    assert enriched.foreground.window_title == "FakeApp"


def test_engine_skips_resolver_for_non_click_events() -> None:
    engine = CaptureEngine(
        foreground_factory=_FakeForeground,
        resolver_factory=_fake_resolver,
    )
    sink = _CollectingSink()
    engine.add_sink(sink)
    engine.start()
    try:
        engine.submit(RawCaptureEvent(kind=EventKind.KEY_PRESS, key="enter"))
        _wait_for(lambda: len(sink.events) == 1)
    finally:
        engine.stop()

    enriched = sink.events[0]
    assert enriched.resolved is None
    assert enriched.raw.png_bytes is None
    assert enriched.image_sha256 == ""


def test_engine_stops_cleanly_without_events() -> None:
    engine = CaptureEngine(
        foreground_factory=_FakeForeground,
        resolver_factory=_fake_resolver,
    )
    engine.start()
    engine.stop()
