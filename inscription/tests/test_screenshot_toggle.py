"""Auto-screenshot toggle.

Verifies that ``ClickSource(auto_screenshot=False)`` and
``WindowFocusSource(auto_screenshot=False)`` skip the screenshot grab
and emit events without ``png_bytes``. We can't drive pynput in a unit
test, but we can poke the source's internal callbacks the same way
``test_scroll_source.py`` does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from inscription.capture.click_source import ClickSource
from inscription.capture.window_source import WindowFocusSource
from inscription.platform import ForegroundInfo, ForegroundInspector

if TYPE_CHECKING:
    from inscription.capture import CaptureEngine, RawCaptureEvent


class _Engine:
    def __init__(self) -> None:
        self.events: list[RawCaptureEvent] = []

    def submit(self, event: RawCaptureEvent) -> bool:
        self.events.append(event)
        return True


class _StubInspector(ForegroundInspector):
    def __init__(self, *, hwnd: int, title: str = "App") -> None:
        self._hwnd = hwnd
        self._title = title

    def inspect(self) -> ForegroundInfo:
        return ForegroundInfo(
            window_title=self._title,
            process_name="app.exe",
            process_id=1,
            hwnd=self._hwnd,
            window_rect=(0, 0, 800, 600),
        )


def test_click_source_skips_screenshot_when_disabled() -> None:
    engine = _Engine()
    src = ClickSource(auto_screenshot=False)
    src._engine = cast("CaptureEngine", engine)

    # Drive the listener callback as pynput would. The Mouse.Button enum
    # isn't reachable headlessly; a stub object with .name suffices.
    class _Btn:
        name = "left"

    src._on_click(120, 240, _Btn(), True)

    assert len(engine.events) == 1
    event = engine.events[0]
    assert event.png_bytes is None
    assert event.x == 120
    assert event.y == 240
    # The lazy ScreenCapturer was never created.
    assert src._screen is None


def test_window_focus_source_skips_screenshot_when_disabled() -> None:
    engine = _Engine()
    inspector = _StubInspector(hwnd=11)
    src = WindowFocusSource(inspector=inspector, auto_screenshot=False)
    src._engine = cast("CaptureEngine", engine)

    # Prime the "previous identity" so the next tick fires an event.
    src._tick()  # establishes hwnd=11 as the baseline; no event
    src._inspector = _StubInspector(hwnd=22)
    src._tick()

    assert len(engine.events) == 1
    assert engine.events[0].png_bytes is None
