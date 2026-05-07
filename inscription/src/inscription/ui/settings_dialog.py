"""Application settings dialog.

Two sections in one window:

- **Examiner identity** — name, organisation, badge / employee ID.
  Saved to :class:`Config` and auto-fills the forensic-notes header.
- **LLM endpoint** — base URL, model, timeout, optional API key, plus
  a "Test connection" button that fires a tiny chat completion against
  the configured server and reports back. The widget itself lives in
  :mod:`suite_common.ui.llm_settings` so CaseGuide shares it.

Saving writes through to ``QSettings`` via :class:`Config.sync`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from suite_common.ui.llm_settings import LlmSettingsGroup

if TYPE_CHECKING:
    from inscription.config import Config

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Edit examiner identity and LLM endpoint configuration."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("Settings")
        self.resize(560, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(self._build_examiner_group())

        # Local-LLM widget shared with CaseGuide. Title carries the
        # purpose-specific suffix so the operator knows which flow this
        # endpoint feeds.
        self._llm_group = LlmSettingsGroup(
            config, title="Local LLM (for AI rewrite)", parent=self
        )
        layout.addWidget(self._llm_group)
        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setProperty("role", "primary")
        # Pressing Enter from any field saves -- the default OS-style
        # behaviour, but Qt's QDialogButtonBox doesn't infer the default
        # button automatically when there are multiple ApplyRole-class
        # candidates. Explicit setDefault means we don't rely on
        # creation-order heuristics.
        save_btn.setDefault(True)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------ examiner

    def _build_examiner_group(self) -> QGroupBox:
        box = QGroupBox("Examiner identity", self)

        self._name_edit = QLineEdit(self._config.examiner_name, box)
        self._name_edit.setPlaceholderText("e.g. Alex Smith")
        self._org_edit = QLineEdit(self._config.examiner_org, box)
        self._org_edit.setPlaceholderText("e.g. Cyber Crimes Unit")
        self._id_edit = QLineEdit(self._config.examiner_id, box)
        self._id_edit.setPlaceholderText("e.g. CCU-0421")

        hint = QLabel(
            "Auto-fills the forensic-notes header so you don't have to "
            "type it on every export.",
            box,
        )
        hint.setProperty("muted", "true")
        hint.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Name", self._name_edit)
        form.addRow("Organisation", self._org_edit)
        form.addRow("Badge / ID", self._id_edit)

        outer = QVBoxLayout(box)
        outer.addLayout(form)
        outer.addWidget(hint)
        return box

    # -------------------------------------------------------- internals

    def _on_save(self) -> None:
        self._config.examiner_name = self._name_edit.text().strip()
        self._config.examiner_org = self._org_edit.text().strip()
        self._config.examiner_id = self._id_edit.text().strip()
        self._llm_group.commit()
        self._config.sync()
        self.accept()

    def done(self, result: int) -> None:
        """Wait for in-flight LLM-settings worker threads before closing.

        The shared widget owns the QThread lifecycle; we just forward
        the dialog-close event so the workers' 3 s HTTP timeouts can
        elapse cleanly instead of dangling past the dialog's
        ``deleteLater``.
        """
        self._llm_group.cancel_workers()
        super().done(result)


def prompt_for_examiner_identity(config: Config, parent: QWidget | None = None) -> bool:
    """First-run helper: open Settings if the examiner hasn't filled in a name.

    Returns True if the user completed (or already had) an identity, False
    if they cancelled. Callers don't have to use this — Settings is
    always reachable from the menu — but the forensic-notes export uses
    it to nudge the user before a header would otherwise read "—".
    """
    if config.has_examiner_identity():
        return True
    QMessageBox.information(
        parent,
        "Examiner identity needed",
        "Set your examiner name and organisation so the notes header is "
        "filled in automatically.",
    )
    dialog = SettingsDialog(config, parent=parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    return config.has_examiner_identity()
