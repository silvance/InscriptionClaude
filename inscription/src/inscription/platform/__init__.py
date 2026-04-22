"""Platform-specific abstractions for Inscription.

The rest of the application talks to platform capabilities through the
interfaces in this package. Each capability has a concrete implementation
keyed off the host OS; the :func:`create_*` factory functions pick the
right one automatically.

Phase 1 ships:

- :class:`ScreenCapturer` — implemented via ``mss`` on all platforms.
- :class:`HotkeyManager` — implemented via ``pynput`` on all platforms.
- :class:`ForegroundInspector` — a stub that returns window title and
  process name via ``psutil``/``pynput``; Phase 3 replaces it on Windows
  with a UIA-backed implementation for per-application context.
"""

from inscription.platform.foreground import (
    ForegroundInfo,
    ForegroundInspector,
    create_foreground_inspector,
)
from inscription.platform.hotkeys import (
    HotkeyBinding,
    HotkeyError,
    HotkeyManager,
    create_hotkey_manager,
)
from inscription.platform.screen import (
    CapturedImage,
    MonitorInfo,
    ScreenCapturer,
    create_screen_capturer,
)

__all__ = [
    "CapturedImage",
    "ForegroundInfo",
    "ForegroundInspector",
    "HotkeyBinding",
    "HotkeyError",
    "HotkeyManager",
    "MonitorInfo",
    "ScreenCapturer",
    "create_foreground_inspector",
    "create_hotkey_manager",
    "create_screen_capturer",
]
