"""End-to-end: capture -> generate -> export."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from inscription.capture import (
    CaptureEngine,
    RawCaptureEvent,
    SessionSink,
)
from inscription.export import export_html
from inscription.model import EventKind, ResolvedElement
from inscription.platform import (
    CapturedImage,
    ForegroundInfo,
    ForegroundInspector,
    MonitorInfo,
    ScreenCapturer,
)
from inscription.resolve import ElementResolver
from inscription.steps import generate_steps
from inscription.storage import SessionRepository

if TYPE_CHECKING:
    from collections.abc import Callable


class _FakeScreen(ScreenCapturer):
    def list_monitors(self) -> list[MonitorInfo]:
        return [MonitorInfo(index=1, left=0, top=0, width=1, height=1)]

    def capture(self, monitor_index: int | None = None) -> CapturedImage:
        # Minimal valid PNG bytes; verified-decodable 1x1.
        data = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae"
            "426082"
        )
        return CapturedImage(png_bytes=data, width=1, height=1, monitor_index=monitor_index or 1)


class _FakeForeground(ForegroundInspector):
    def inspect(self) -> ForegroundInfo:
        return ForegroundInfo(
            window_title="DemoApp",
            process_name="demo.exe",
            process_id=123,
        )


class _FakeResolver(ElementResolver):
    def resolve_at(self, x: int, y: int) -> ResolvedElement:
        return ResolvedElement(
            id=None,
            name="Submit",
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


def test_capture_generate_export(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Integration")
    try:
        engine = CaptureEngine(
            screen_factory=_FakeScreen,
            foreground_factory=_FakeForeground,
            resolver_factory=_fake_resolver,
        )
        sink = SessionSink(repo)
        engine.add_sink(sink)
        engine.start()
        try:
            engine.submit(RawCaptureEvent(kind=EventKind.CLICK, x=5, y=5, button="left"))
            _wait_for(lambda: len(repo.list_events()) == 1)
        finally:
            engine.stop()

        events = repo.list_events()
        assert len(events) == 1
        assert events[0].resolved_element_id is not None
        assert events[0].screenshot_id is not None

        steps = generate_steps(repo)
        assert steps
        assert "Submit" in steps[0].text

        doc = export_html(repo)
    finally:
        repo.close()

    html_text = doc.path.read_text(encoding="utf-8")
    assert "Submit" in html_text
