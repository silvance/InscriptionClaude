"""Integration tests for the capture engine and its sources/sinks.

These tests stub out the platform layer (no real screen grabs or hotkeys)
but exercise the full producer/consumer flow end-to-end against a real
SQLite-backed :class:`CaseRepository`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from inscription.capture.engine import (
    CaptureEngine,
    CaptureRequest,
    CaptureResult,
    CaptureSink,
)
from inscription.capture.hotkey_source import HotkeyCaptureBinding, HotkeySource
from inscription.capture.repository_sink import CaseRepositorySink
from inscription.cases.models import StepKind
from inscription.platform import (
    CapturedImage,
    ForegroundInfo,
    ForegroundInspector,
    HotkeyBinding,
    MonitorInfo,
    ScreenCapturer,
)
from inscription.platform.hotkeys import _StubHotkeyManager
from inscription.storage import CaseRepository

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


# ---------------------------------------------------------------- fakes


class _FakeScreenCapturer(ScreenCapturer):
    def __init__(self) -> None:
        self.capture_calls = 0

    def list_monitors(self) -> list[MonitorInfo]:
        return [MonitorInfo(index=1, left=0, top=0, width=100, height=100)]

    def capture(self, monitor_index: int | None = None) -> CapturedImage:
        self.capture_calls += 1
        return CapturedImage(
            png_bytes=b"\x89PNG\r\n\x1a\nFAKE",
            width=100,
            height=100,
            monitor_index=monitor_index or 1,
        )


class _FakeForegroundInspector(ForegroundInspector):
    def inspect(self) -> ForegroundInfo:
        return ForegroundInfo(
            window_title="Fake Window",
            process_name="fake.exe",
            process_id=1234,
        )


@dataclass
class _RecordingSink(CaptureSink):
    results: list[CaptureResult]

    def handle(self, result: CaptureResult) -> None:
        self.results.append(result)


# ---------------------------------------------------------------- helpers


@pytest.fixture
def engine() -> CaptureEngine:
    return CaptureEngine(
        screen_capturer=_FakeScreenCapturer(),
        foreground_inspector=_FakeForegroundInspector(),
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 2.0) -> None:
    """Poll ``predicate`` until true or ``timeout`` expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    msg = "Predicate did not become true within timeout"
    raise AssertionError(msg)


# ---------------------------------------------------------------- engine


def test_engine_routes_requests_to_sinks(engine: CaptureEngine) -> None:
    sink = _RecordingSink(results=[])
    engine.add_sink(sink)
    engine.start()
    try:
        engine.submit(CaptureRequest(kind=StepKind.HOTKEY_CAPTURE, title_hint="first"))
        engine.submit(CaptureRequest(kind=StepKind.MANUAL_NOTE, title_hint="second"))
        _wait_for(lambda: len(sink.results) == 2)
    finally:
        engine.stop()

    assert [r.request.title_hint for r in sink.results] == ["first", "second"]
    assert sink.results[0].image.png_bytes.startswith(b"\x89PNG")


def test_engine_submit_returns_false_when_stopping(engine: CaptureEngine) -> None:
    engine.start()
    engine.stop()
    accepted = engine.submit(CaptureRequest(kind=StepKind.MANUAL_NOTE))
    assert accepted is False


def test_engine_fans_out_to_multiple_sinks(engine: CaptureEngine) -> None:
    sink_a = _RecordingSink(results=[])
    sink_b = _RecordingSink(results=[])
    engine.add_sink(sink_a)
    engine.add_sink(sink_b)
    engine.start()
    try:
        engine.submit(CaptureRequest(kind=StepKind.HOTKEY_CAPTURE))
        _wait_for(lambda: len(sink_a.results) == 1 and len(sink_b.results) == 1)
    finally:
        engine.stop()


def test_engine_failing_sink_does_not_affect_others(engine: CaptureEngine) -> None:
    class _ExplodingSink(CaptureSink):
        def handle(self, result: CaptureResult) -> None:
            raise RuntimeError("boom")

    good = _RecordingSink(results=[])
    engine.add_sink(_ExplodingSink())
    engine.add_sink(good)
    engine.start()
    try:
        engine.submit(CaptureRequest(kind=StepKind.HOTKEY_CAPTURE))
        _wait_for(lambda: len(good.results) == 1)
    finally:
        engine.stop()


# ---------------------------------------------------------------- hotkey source


def test_hotkey_source_wires_callbacks_to_engine(engine: CaptureEngine) -> None:
    hotkeys = _StubHotkeyManager()
    source = HotkeySource(
        hotkey_manager=hotkeys,
        bindings=(
            HotkeyCaptureBinding(
                sequence="<ctrl>+<shift>+s",
                name="cap",
                kind=StepKind.HOTKEY_CAPTURE,
            ),
        ),
    )
    sink = _RecordingSink(results=[])
    engine.add_sink(sink)
    engine.add_source(source)
    engine.start()
    try:
        hotkeys.trigger("<ctrl>+<shift>+s")
        _wait_for(lambda: len(sink.results) == 1)
    finally:
        engine.stop()

    assert sink.results[0].request.kind == StepKind.HOTKEY_CAPTURE
    assert sink.results[0].request.title_hint == "cap"


def test_hotkey_source_stop_clears_registrations() -> None:
    hotkeys = _StubHotkeyManager()
    source = HotkeySource(
        hotkey_manager=hotkeys,
        bindings=(
            HotkeyCaptureBinding(sequence="<ctrl>+1", name="a", kind=StepKind.HOTKEY_CAPTURE),
        ),
    )
    # No engine needed for this test; start() with a dummy engine then stop.
    engine = CaptureEngine(
        screen_capturer=_FakeScreenCapturer(),
        foreground_inspector=_FakeForegroundInspector(),
    )
    source.start(engine)
    assert hotkeys.is_active()
    source.stop()
    assert not hotkeys.is_active()


# ---------------------------------------------------------------- repo sink


def test_repo_sink_persists_screenshot_and_step(workspace: Path) -> None:
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-5001",
        title="Capture flow",
        examiner="James",
    )
    try:
        session = repo.start_session()
        assert session.id is not None

        sink = CaseRepositorySink(repo)
        sink.set_session(session.id)

        engine = CaptureEngine(
            screen_capturer=_FakeScreenCapturer(),
            foreground_inspector=_FakeForegroundInspector(),
        )
        engine.add_sink(sink)
        engine.start()
        try:
            engine.submit(CaptureRequest(kind=StepKind.HOTKEY_CAPTURE, title_hint="A"))
            engine.submit(CaptureRequest(kind=StepKind.HOTKEY_CAPTURE, title_hint="B"))
            _wait_for(lambda: len(repo.list_steps(session.id)) == 2)
        finally:
            engine.stop()

        steps = repo.list_steps(session.id)
        assert [s.title for s in steps] == ["A", "B"]
        assert all(s.screenshot_path is not None for s in steps)
        # The files actually exist on disk.
        for step in steps:
            assert step.screenshot_path is not None
            assert (repo.case.root / step.screenshot_path).is_file()
    finally:
        repo.close()


def test_repo_sink_falls_back_to_foreground_title(workspace: Path) -> None:
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-5002",
        title="Title fallback",
        examiner="James",
    )
    try:
        session = repo.start_session()
        assert session.id is not None
        sink = CaseRepositorySink(repo)
        sink.set_session(session.id)

        engine = CaptureEngine(
            screen_capturer=_FakeScreenCapturer(),
            foreground_inspector=_FakeForegroundInspector(),
        )
        engine.add_sink(sink)
        engine.start()
        try:
            engine.submit(CaptureRequest(kind=StepKind.HOTKEY_CAPTURE))  # empty hint
            _wait_for(lambda: len(repo.list_steps(session.id)) == 1)
        finally:
            engine.stop()

        step = repo.list_steps(session.id)[0]
        assert step.title == "Fake Window"  # from _FakeForegroundInspector
    finally:
        repo.close()


def test_repo_sink_drops_captures_without_session(workspace: Path) -> None:
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-5003",
        title="No session",
        examiner="James",
    )
    try:
        sink = CaseRepositorySink(repo)  # set_session not called

        engine = CaptureEngine(
            screen_capturer=_FakeScreenCapturer(),
            foreground_inspector=_FakeForegroundInspector(),
        )
        engine.add_sink(sink)
        engine.start()
        try:
            engine.submit(CaptureRequest(kind=StepKind.HOTKEY_CAPTURE))
            # Wait a beat to ensure the request is processed, then verify.
            time.sleep(0.1)
        finally:
            engine.stop()

        # No session => nothing persisted, but also no crash.
        assert repo.list_steps() == []
    finally:
        repo.close()


# ---------------------------------------------------------------- unused


def test_hotkeybinding_frozen() -> None:
    # Sanity: HotkeyBinding dataclass is frozen.
    binding = HotkeyBinding(sequence="<ctrl>+a", name="x")
    with pytest.raises(Exception):  # noqa: B017, PT011  - frozen dataclass raises FrozenInstanceError
        binding.sequence = "<ctrl>+b"  # type: ignore[misc]
