"""Typed wrapper around ``QSettings`` for Inscription configuration.

Settings live in an INI file at :data:`inscription.paths.CONFIG_FILE` so
they can be inspected and edited outside the application when needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QByteArray, QSettings

from inscription.paths import CONFIG_FILE, WORKSPACE_DIR

_K_WINDOW_GEOMETRY: Final = "window/geometry"
_K_WINDOW_STATE: Final = "window/state"
_K_WORKSPACE_ROOT: Final = "storage/workspace_root"
_K_THEME: Final = "ui/theme"


class Config:
    """Typed access to user configuration, backed by a QSettings INI file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or CONFIG_FILE
        self._qs = QSettings(str(self._path), QSettings.Format.IniFormat)

    # ------------------------------------------------------------ window

    @property
    def window_geometry(self) -> QByteArray | None:
        val = self._qs.value(_K_WINDOW_GEOMETRY)
        if isinstance(val, QByteArray) and not val.isEmpty():
            return val
        return None

    @window_geometry.setter
    def window_geometry(self, value: QByteArray) -> None:
        self._qs.setValue(_K_WINDOW_GEOMETRY, value)

    @property
    def window_state(self) -> QByteArray | None:
        val = self._qs.value(_K_WINDOW_STATE)
        if isinstance(val, QByteArray) and not val.isEmpty():
            return val
        return None

    @window_state.setter
    def window_state(self, value: QByteArray) -> None:
        self._qs.setValue(_K_WINDOW_STATE, value)

    # ----------------------------------------------------------- storage

    @property
    def workspace_root(self) -> Path:
        """Root directory for all session folders on this machine."""
        val = self._qs.value(_K_WORKSPACE_ROOT, "")
        return Path(str(val)) if val else WORKSPACE_DIR

    @workspace_root.setter
    def workspace_root(self, value: Path) -> None:
        self._qs.setValue(_K_WORKSPACE_ROOT, str(value))

    # ---------------------------------------------------------------- ui

    @property
    def theme(self) -> str:
        return str(self._qs.value(_K_THEME, "system"))

    @theme.setter
    def theme(self, value: str) -> None:
        self._qs.setValue(_K_THEME, value)

    # ------------------------------------------------------- persistence

    def sync(self) -> None:
        """Flush pending writes to disk."""
        self._qs.sync()
