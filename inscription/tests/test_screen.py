"""Screen capturer multi-monitor dispatch."""

from __future__ import annotations

from inscription.platform import CapturedImage, MonitorInfo, ScreenCapturer


class _TwoMonitorCapturer(ScreenCapturer):
    """Two 1920x1080 monitors side by side at (0,0) and (1920,0)."""

    def __init__(self) -> None:
        self.captured_index: int | None = None

    def list_monitors(self) -> list[MonitorInfo]:
        return [
            MonitorInfo(index=0, left=0, top=0, width=3840, height=1080),  # virtual
            MonitorInfo(index=1, left=0, top=0, width=1920, height=1080),
            MonitorInfo(index=2, left=1920, top=0, width=1920, height=1080),
        ]

    def capture(self, monitor_index: int | None = None) -> CapturedImage:
        idx = monitor_index if monitor_index is not None else 1
        self.captured_index = idx
        return CapturedImage(png_bytes=b"x", width=1, height=1, monitor_index=idx)


def test_capture_at_picks_primary_for_left_monitor_click() -> None:
    cap = _TwoMonitorCapturer()
    cap.capture_at(500, 500)
    assert cap.captured_index == 1


def test_capture_at_picks_secondary_for_right_monitor_click() -> None:
    cap = _TwoMonitorCapturer()
    cap.capture_at(2500, 500)
    assert cap.captured_index == 2


def test_capture_at_falls_back_to_primary_for_out_of_bounds() -> None:
    cap = _TwoMonitorCapturer()
    cap.capture_at(-100, -100)
    assert cap.captured_index == 1


def test_capture_at_skips_the_virtual_monitor_entry() -> None:
    cap = _TwoMonitorCapturer()
    cap.capture_at(10, 10)
    # Would be 0 if we matched against the virtual "all monitors" entry.
    assert cap.captured_index == 1
