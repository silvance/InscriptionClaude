"""Platform-specific abstractions for Inscription.

The rest of the application talks to platform capabilities through the
interfaces in this package. Each capability has a concrete implementation
keyed off the host OS; the :func:`create_*` factory functions pick the
right one automatically.

- :class:`ScreenCapturer` — implemented via ``mss`` on all platforms.
- :class:`HotkeyManager` — implemented via ``pynput`` on all platforms.
- :class:`ForegroundInspector` — reads foreground window title and process
  name. The Windows implementation uses ``ctypes`` + ``psutil``; UIA
  element lookup sits in :mod:`inscription.resolve`, not here.
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
    safe_close,
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
    "safe_close",
]
