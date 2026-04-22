"""Tests for the platform abstraction package.

We exercise the abstract interfaces plus the stub and mss implementations.
The pynput and Windows-specific inspectors are exercised only through the
``create_*`` factories, with fallbacks verified.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from inscription.platform import (
    HotkeyBinding,
    create_foreground_inspector,
    create_hotkey_manager,
    create_screen_capturer,
)
from inscription.platform.hotkeys import _StubHotkeyManager
from inscription.platform.screen import (
    CapturedImage,
    MonitorInfo,
    MssScreenCapturer,
    _NullScreenCapturer,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------- screen


def test_null_capturer_returns_valid_png() -> None:
    cap = _NullScreenCapturer()
    img = cap.capture()
    assert isinstance(img, CapturedImage)
    assert img.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert img.width == 1
    assert img.height == 1


def test_null_capturer_lists_one_monitor() -> None:
    cap = _NullScreenCapturer()
    monitors = cap.list_monitors()
    assert len(monitors) == 1
    assert isinstance(monitors[0], MonitorInfo)


def test_null_capturer_capture_to_file(tmp_path: Path) -> None:
    cap = _NullScreenCapturer()
    target = tmp_path / "shot.png"
    img = cap.capture_to_file(target)
    assert target.exists()
    assert target.read_bytes() == img.png_bytes


def test_create_screen_capturer_returns_something() -> None:
    # Should succeed on any platform — either mss or null fallback.
    cap = create_screen_capturer()
    try:
        monitors = cap.list_monitors()
        assert len(monitors) >= 1
    finally:
        cap.close()


def test_mss_capturer_handles_bad_monitor_index() -> None:
    # Only run the real mss test if mss actually initialised.
    try:
        cap = MssScreenCapturer()
    except Exception:
        pytest.skip("mss cannot initialise in this environment")
    try:
        with pytest.raises(IndexError):
            cap.capture(monitor_index=999)
    finally:
        cap.close()


# ---------------------------------------------------------------- hotkeys


def test_stub_hotkey_manager_triggers_callback() -> None:
    mgr = _StubHotkeyManager()
    fired: list[str] = []
    mgr.register(
        HotkeyBinding(sequence="<ctrl>+<shift>+s", name="capture"),
        lambda: fired.append("capture"),
    )
    assert mgr.is_active()
    mgr.trigger("<ctrl>+<shift>+s")
    assert fired == ["capture"]


def test_stub_hotkey_manager_unregister_all() -> None:
    mgr = _StubHotkeyManager()
    mgr.register(HotkeyBinding(sequence="<ctrl>+a"), lambda: None)
    mgr.unregister_all()
    assert not mgr.is_active()
    with pytest.raises(KeyError):
        mgr.trigger("<ctrl>+a")


def test_stub_hotkey_manager_context_manager() -> None:
    with create_hotkey_manager(use_stub=True) as mgr:
        mgr.register(HotkeyBinding(sequence="<ctrl>+b"), lambda: None)
        assert mgr.is_active()
    assert not mgr.is_active()


def test_create_hotkey_manager_use_stub() -> None:
    mgr = create_hotkey_manager(use_stub=True)
    assert isinstance(mgr, _StubHotkeyManager)


# ---------------------------------------------------------------- foreground


def test_create_foreground_inspector_returns_something() -> None:
    inspector = create_foreground_inspector()
    info = inspector.inspect()
    # Window title may be empty on Linux / CI but the dataclass must be valid.
    assert isinstance(info.window_title, str)
    assert isinstance(info.process_name, str)
