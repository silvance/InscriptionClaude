"""Typed wrapper around ``QSettings`` for Inscription configuration.

Settings are stored in an INI file at :data:`inscription.paths.CONFIG_FILE`
so they can be inspected and edited outside the application when needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QByteArray, QSettings

from inscription.paths import CONFIG_FILE, WORKSPACE_DIR

_K_WINDOW_GEOMETRY: Final = "window/geometry"
_K_WINDOW_STATE: Final = "window/state"
_K_NAS_ROOT: Final = "storage/nas_root"
_K_WORKSPACE_ROOT: Final = "storage/workspace_root"
_K_THEME: Final = "ui/theme"
_K_CASE_NUMBER_REGEX: Final = "cases/number_regex"

#: Default regex matching e.g. ``HSV-2026-0317``. Overridable per-site.
DEFAULT_CASE_NUMBER_REGEX: Final = r"^[A-Z]{2,5}-\d{4}-\d{3,5}$"


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
    def nas_root(self) -> Path | None:
        """Network path where canonical case data lives.

        ``None`` until the user configures it on first run.
        """
        val = self._qs.value(_K_NAS_ROOT, "")
        return Path(str(val)) if val else None

    @nas_root.setter
    def nas_root(self, value: Path | None) -> None:
        self._qs.setValue(_K_NAS_ROOT, str(value) if value else "")

    @property
    def workspace_root(self) -> Path:
        """Local workspace directory. Defaults to :data:`paths.WORKSPACE_DIR`."""
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

    # ------------------------------------------------------------- cases

    @property
    def case_number_regex(self) -> str:
        return str(self._qs.value(_K_CASE_NUMBER_REGEX, DEFAULT_CASE_NUMBER_REGEX))

    @case_number_regex.setter
    def case_number_regex(self, value: str) -> None:
        self._qs.setValue(_K_CASE_NUMBER_REGEX, value)

    # ------------------------------------------------------- persistence

    def sync(self) -> None:
        """Flush pending writes to disk."""
        self._qs.sync()
