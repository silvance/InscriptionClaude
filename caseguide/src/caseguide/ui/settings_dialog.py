"""Application settings dialog for CaseGuide.

CaseGuide's settings surface is narrower than Inscription's by design —
the case metadata (examiner identity, case scope) belongs to CaseForge
and propagates via ``case.json``, so the only thing CaseGuide owns at
the user level is the LLM endpoint that powers the Refine pass.

The LLM widget itself lives in :mod:`suite_common.ui.llm_settings` so
Inscription and CaseGuide share a single implementation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from suite_common.ui.llm_settings import LlmSettingsGroup

if TYPE_CHECKING:
    from caseguide.config import Config

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Edit the LLM endpoint configuration."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("Settings")
        self.resize(520, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._llm_group = LlmSettingsGroup(
            config, title="Local LLM (for Refine)", parent=self
        )
        layout.addWidget(self._llm_group)

        hint = QLabel(
            "These match Inscription's LLM settings — point both apps "
            "at the same local Ollama / LM Studio instance.",
            self,
        )
        hint.setProperty("muted", "true")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setProperty("role", "primary")
        # Enter saves; explicit setDefault rather than relying on
        # creation-order heuristics inside QDialogButtonBox.
        save_btn.setDefault(True)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -------------------------------------------------------- internals

    def _on_save(self) -> None:
        self._llm_group.commit()
        self._config.sync()
        self.accept()

    def done(self, result: int) -> None:
        """Wait for in-flight LLM-settings worker threads before closing."""
        self._llm_group.cancel_workers()
        super().done(result)
