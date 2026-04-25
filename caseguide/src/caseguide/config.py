"""Typed wrapper around ``QSettings`` for CaseGuide configuration.

Mirrors Inscription's config pattern so the LLM endpoint settings line
up — same defaults pointing at Ollama on localhost, same examiner
expectation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QByteArray, QSettings

from caseguide.paths import CONFIG_FILE

_K_WINDOW_GEOMETRY: Final = "window/geometry"
_K_WINDOW_STATE: Final = "window/state"
_K_LLM_BASE_URL: Final = "llm/base_url"
_K_LLM_MODEL: Final = "llm/model"
_K_LLM_TIMEOUT_S: Final = "llm/timeout_s"
_K_LLM_API_KEY: Final = "llm/api_key"
_K_RECENT_CASE_PATHS: Final = "browser/recent_case_paths"

#: Defaults match Inscription's so a single Ollama instance serves both.
DEFAULT_LLM_BASE_URL: Final = "http://localhost:11434/v1"
DEFAULT_LLM_MODEL: Final = "gemma4:latest"
DEFAULT_LLM_TIMEOUT_S: Final = 180.0


class Config:
    """Typed access to user configuration."""

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

    # --------------------------------------------------------------- llm

    @property
    def llm_base_url(self) -> str:
        return str(self._qs.value(_K_LLM_BASE_URL, DEFAULT_LLM_BASE_URL))

    @llm_base_url.setter
    def llm_base_url(self, value: str) -> None:
        self._qs.setValue(_K_LLM_BASE_URL, value)

    @property
    def llm_model(self) -> str:
        return str(self._qs.value(_K_LLM_MODEL, DEFAULT_LLM_MODEL))

    @llm_model.setter
    def llm_model(self, value: str) -> None:
        self._qs.setValue(_K_LLM_MODEL, value)

    @property
    def llm_timeout_s(self) -> float:
        raw = self._qs.value(_K_LLM_TIMEOUT_S, DEFAULT_LLM_TIMEOUT_S)
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            try:
                return float(raw)
            except ValueError:
                pass
        return DEFAULT_LLM_TIMEOUT_S

    @llm_timeout_s.setter
    def llm_timeout_s(self, value: float) -> None:
        self._qs.setValue(_K_LLM_TIMEOUT_S, float(value))

    @property
    def llm_api_key(self) -> str | None:
        val = self._qs.value(_K_LLM_API_KEY, "")
        return str(val) if val else None

    @llm_api_key.setter
    def llm_api_key(self, value: str | None) -> None:
        self._qs.setValue(_K_LLM_API_KEY, value or "")

    # ----------------------------------------------------------- browser

    @property
    def recent_case_paths(self) -> list[str]:
        raw = str(self._qs.value(_K_RECENT_CASE_PATHS, ""))
        return [p for p in raw.split(";") if p]

    @recent_case_paths.setter
    def recent_case_paths(self, value: list[str]) -> None:
        self._qs.setValue(_K_RECENT_CASE_PATHS, ";".join(value))

    def remember_case(self, case_path: str, *, limit: int = 12) -> None:
        existing = [p for p in self.recent_case_paths if p != case_path]
        self.recent_case_paths = [case_path, *existing][:limit]

    # ------------------------------------------------------- persistence

    def sync(self) -> None:
        self._qs.sync()
