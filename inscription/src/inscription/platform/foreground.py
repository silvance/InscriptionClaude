"""Foreground window / process inspection.

Phase 1 provides a basic implementation returning window title and process
name; Phase 3 replaces the Windows variant with a UIA-backed inspector that
extracts per-suite forensic-tool context (AXIOM artifact path, X-Ways
evidence item, etc.).
"""

from __future__ import annotations

import ctypes
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class ForegroundInfo:
    """Snapshot of what was in the foreground at capture time."""

    window_title: str
    process_name: str
    process_id: int | None
    #: Absolute path to the executable, if resolvable.
    process_path: str | None = None
    #: Free-form dict for provider-specific context (Phase 3+).
    extras: dict[str, str] | None = None


class ForegroundInspector(ABC):
    @abstractmethod
    def inspect(self) -> ForegroundInfo:
        """Return a snapshot of the current foreground window."""


class _UnknownForegroundInspector(ForegroundInspector):
    """Fallback returning placeholder info when no real implementation applies."""

    def inspect(self) -> ForegroundInfo:
        return ForegroundInfo(
            window_title="",
            process_name="",
            process_id=os.getpid(),
            process_path=None,
        )


class _WindowsForegroundInspector(ForegroundInspector):
    """Windows implementation using the Win32 API via ``ctypes``.

    Avoids a dependency on ``pywin32`` by calling ``user32`` directly.
    Phase 3 will subclass or replace this with a pywinauto-based inspector
    that also reads UIA trees.
    """

    def inspect(self) -> ForegroundInfo:
        # ctypes.windll only exists on Windows; guard to stay importable.
        windll = getattr(ctypes, "windll", None)
        if windll is None:  # pragma: no cover - only hit on non-Windows
            return _UnknownForegroundInspector().inspect()

        from ctypes import wintypes  # noqa: PLC0415 - Windows-only symbol

        user32 = windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return _UnknownForegroundInspector().inspect()

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_id: int | None = int(pid.value) or None

        process_name = ""
        process_path: str | None = None
        if process_id is not None:
            try:
                proc = psutil.Process(process_id)
                process_name = proc.name()
                process_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("psutil lookup failed for PID %d: %s", process_id, exc)

        return ForegroundInfo(
            window_title=title,
            process_name=process_name,
            process_id=process_id,
            process_path=process_path,
        )


class _LinuxForegroundInspector(ForegroundInspector):
    """Best-effort Linux inspector. Phase 1 only needs something non-empty.

    Proper X11/Wayland active-window detection (via python-xlib or
    xdotool) is not worth the complexity for Phase 1 — forensic context
    extraction that matters for evidence is Windows-only and belongs in
    Phase 3's suite-specific adapters.
    """

    def inspect(self) -> ForegroundInfo:
        return ForegroundInfo(
            window_title="",
            process_name="",
            process_id=os.getpid(),
            process_path=None,
        )


def create_foreground_inspector() -> ForegroundInspector:
    """Return a foreground inspector appropriate for the current OS."""
    if os.name == "nt":
        return _WindowsForegroundInspector()
    return _LinuxForegroundInspector()
