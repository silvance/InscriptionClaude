"""WindowFocusSource identity keying.

The source keys "did the window change?" on the native handle when
available, not on the title. This stops Notepad-style title updates
(``"*h - Notepad"`` → ``"*he - Notepad"``) from producing one spurious
switch event per keystroke.
"""

from __future__ import annotations

from inscription.capture.window_source import _identity
from inscription.platform import ForegroundInfo


def _info(*, title: str, hwnd: int | None, process: str = "notepad.exe") -> ForegroundInfo:
    return ForegroundInfo(
        window_title=title,
        process_name=process,
        process_id=1,
        hwnd=hwnd,
    )


def test_same_hwnd_different_title_is_the_same_window() -> None:
    a = _info(title="*h - Notepad", hwnd=12345)
    b = _info(title="*he - Notepad", hwnd=12345)
    assert _identity(a) == _identity(b)


def test_different_hwnd_same_title_is_a_different_window() -> None:
    a = _info(title="Untitled - Notepad", hwnd=111)
    b = _info(title="Untitled - Notepad", hwnd=222)
    assert _identity(a) != _identity(b)


def test_falls_back_to_title_when_no_hwnd() -> None:
    a = _info(title="Foo", hwnd=None)
    b = _info(title="Bar", hwnd=None)
    assert _identity(a) != _identity(b)
    c = _info(title="Foo", hwnd=None)
    assert _identity(a) == _identity(c)


def test_process_name_distinguishes_windows_with_same_hwnd_value() -> None:
    # Pathological but cheap to guard: a zero hwnd from a stub inspector
    # shouldn't let two unrelated apps collapse to the same identity.
    a = _info(title="A", hwnd=0, process="a.exe")
    b = _info(title="B", hwnd=0, process="b.exe")
    assert _identity(a) != _identity(b)
