"""Global hotkey abstraction.

Backed by ``pynput``, which works on Windows, macOS, and Linux. On Linux
the listener uses X11 / Wayland primitives and will not capture keys when
the target window has exclusive grab (rare). On Windows it hooks the OS-
level keyboard hook and works across suite windows.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

# pynput attempts to open an X/Wayland/Win32 connection at import time on
# some platforms (notably Linux without DISPLAY). That's fatal at module
# load, so we import defensively and fall back to the stub when unavailable.
try:
    from pynput import keyboard as _pynput_keyboard

    _PYNPUT_AVAILABLE = True
except Exception:  # pynput raises varied backend errors
    _pynput_keyboard = None
    _PYNPUT_AVAILABLE = False

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class HotkeyError(Exception):
    """Raised when hotkey registration fails (parse error, OS error, etc.)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class HotkeyBinding:
    """A parsed hotkey binding ready for registration."""

    #: pynput-format hotkey string, e.g. ``<ctrl>+<shift>+s``.
    sequence: str
    #: Opaque name used in logs and in collision diagnostics.
    name: str = field(default="")


class HotkeyManager(ABC):
    """Register and release global hotkeys."""

    @abstractmethod
    def register(self, binding: HotkeyBinding, callback: Callable[[], None]) -> None:
        """Register a hotkey. Overwrites any existing binding with the same sequence."""

    @abstractmethod
    def unregister_all(self) -> None:
        """Release all bindings and stop any listener threads."""

    @abstractmethod
    def is_active(self) -> bool:
        """True if a listener is currently running."""

    def __enter__(self) -> HotkeyManager:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.unregister_all()


class PynputHotkeyManager(HotkeyManager):
    """``pynput``-backed implementation.

    Uses ``pynput.keyboard.GlobalHotKeys`` which runs a daemon listener
    thread. Registering additional hotkeys requires restarting the listener;
    we handle that transparently.
    """

    def __init__(self) -> None:
        self._bindings: dict[str, Callable[[], None]] = {}
        # Listener is pynput.keyboard.GlobalHotKeys; typed as Any to keep
        # this module importable without a pynput stubs dependency.
        self._listener: Any = None
        self._lock = threading.Lock()

    def register(self, binding: HotkeyBinding, callback: Callable[[], None]) -> None:
        with self._lock:
            self._bindings[binding.sequence] = callback
            self._restart_listener()
            logger.info(
                "Registered hotkey %s (%s) -> %s",
                binding.sequence,
                binding.name or "unnamed",
                callback,
            )

    def unregister_all(self) -> None:
        with self._lock:
            self._bindings.clear()
            self._stop_listener()

    def is_active(self) -> bool:
        return self._listener is not None

    # ---------- listener lifecycle ----------

    def _stop_listener(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Error stopping hotkey listener: %s", exc)
            self._listener = None

    def _restart_listener(self) -> None:
        self._stop_listener()
        if not self._bindings:
            return
        if not _PYNPUT_AVAILABLE:
            msg = "pynput is not available on this platform"
            raise HotkeyError(msg)
        try:
            listener = _pynput_keyboard.GlobalHotKeys(self._bindings)
        except ValueError as exc:
            msg = f"Invalid hotkey sequence: {exc}"
            raise HotkeyError(msg) from exc

        listener.daemon = True
        listener.start()
        self._listener = listener


class _StubHotkeyManager(HotkeyManager):
    """In-process stand-in used when no global hotkey system is available.

    Real registration is a no-op; :meth:`trigger` lets tests and dev tooling
    fire the callback programmatically. Useful for CI and for the menu-
    driven "fire capture" action during development on Linux.
    """

    def __init__(self) -> None:
        self._bindings: dict[str, Callable[[], None]] = {}

    def register(self, binding: HotkeyBinding, callback: Callable[[], None]) -> None:
        self._bindings[binding.sequence] = callback
        logger.info("Stub hotkey registered: %s (%s)", binding.sequence, binding.name)

    def unregister_all(self) -> None:
        self._bindings.clear()

    def is_active(self) -> bool:
        return bool(self._bindings)

    def trigger(self, sequence: str) -> None:
        """Invoke a registered callback as if the hotkey had fired.

        Raises:
            KeyError: If ``sequence`` was never registered.
        """
        self._bindings[sequence]()


def create_hotkey_manager(*, use_stub: bool = False) -> HotkeyManager:
    """Return a hotkey manager appropriate for the environment.

    Falls back to the stub implementation if ``pynput`` is unavailable —
    typically when running headless without a display server.
    """
    if use_stub or not _PYNPUT_AVAILABLE:
        if not use_stub:
            logger.warning("pynput unavailable (no display server?); using stub hotkey manager")
        return _StubHotkeyManager()
    return PynputHotkeyManager()
