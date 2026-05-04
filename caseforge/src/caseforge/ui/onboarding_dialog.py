"""First-run onboarding dialog.

Shown once when the operator launches CaseForge against an unconfigured
profile. Captures examiner name (so new cases pre-fill correctly) and
the workspace folder where cases will live. Skipping is allowed — the
flag is still set so we don't nag — and Settings covers everything
this dialog touches if they want to revisit it later.
"""

from __future__ import annotations

import getpass
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from caseforge.config import Config

logger = logging.getLogger(__name__)


def _default_visible_workspace() -> Path:
    """Suggest ``~/Documents/CaseForge`` as the default workspace.

    Documents is visible to the operator in Explorer / Finder, unlike
    the LOCALAPPDATA-rooted fallback in :mod:`caseforge.paths`. We don't
    require Documents to exist (it almost always does on Windows), and
    if the path can't be resolved we fall back to the home directory.
    """
    try:
        home = Path.home()
    except (RuntimeError, OSError):
        return Path.cwd() / "CaseForge"
    documents = home / "Documents"
    base = documents if documents.is_dir() else home
    return base / "CaseForge"


def _suggested_examiner_name() -> str:
    """Best-effort OS username, title-cased, for pre-fill only."""
    try:
        raw = getpass.getuser()
    except (OSError, KeyError):
        return ""
    return raw.replace("_", " ").replace(".", " ").strip().title()


class OnboardingDialog(QDialog):
    """Two-field welcome form: examiner name + workspace folder."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Welcome to CaseForge")
        self.setModal(True)
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Welcome to CaseForge", self)
        title.setProperty("role", "title")
        layout.addWidget(title)

        intro = QLabel(
            "Two quick questions and you're set up. You can change either of "
            "these any time from <b>Edit &rarr; Settings</b>.",
            self,
        )
        intro.setWordWrap(True)
        intro.setProperty("muted", "true")
        layout.addWidget(intro)

        existing_name = config.examiner_name or _suggested_examiner_name()
        self._name_edit = QLineEdit(existing_name, self)
        self._name_edit.setPlaceholderText("e.g. Alex Smith")

        existing_ws = (
            str(config.workspace_root)
            if config.has_explicit_workspace
            else str(_default_visible_workspace())
        )
        self._workspace_edit = QLineEdit(existing_ws, self)
        workspace_btn = QPushButton("Browse…", self)
        workspace_btn.clicked.connect(self._pick_workspace)
        ws_row = QHBoxLayout()
        ws_row.addWidget(self._workspace_edit, 1)
        ws_row.addWidget(workspace_btn)

        form = QFormLayout()
        form.addRow("Your name", self._name_edit)
        form.addRow("Case workspace", ws_row)
        layout.addLayout(form)

        ws_hint = QLabel(
            "Each case is a folder inside the workspace. Pick somewhere you can "
            "find later — operators usually choose a folder under Documents or "
            "an evidence drive.",
            self,
        )
        ws_hint.setWordWrap(True)
        ws_hint.setProperty("muted", "true")
        layout.addWidget(ws_hint)

        self._error_label = QLabel("", self)
        self._error_label.setProperty("role", "danger")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        skip_btn = QPushButton("Skip for now", self)
        skip_btn.clicked.connect(self._on_skip)
        save_btn = QPushButton("Get started", self)
        save_btn.setProperty("role", "primary")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        button_row.addStretch(1)
        button_row.addWidget(skip_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

    # -------------------------------------------------------- internals

    def _pick_workspace(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select case workspace", self._workspace_edit.text()
        )
        if directory:
            self._workspace_edit.setText(directory)

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        ws_text = self._workspace_edit.text().strip()
        if not ws_text:
            self._show_error("Pick a workspace folder before continuing, or hit Skip.")
            return
        ws_path = Path(ws_text).expanduser()
        try:
            ws_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create workspace at %s: %s", ws_path, exc)
            self._show_error(
                f"Couldn't create that folder: {exc}. Pick somewhere writable."
            )
            return
        self._config.examiner_name = name
        self._config.workspace_root = ws_path
        self._config.onboarding_completed = True
        self._config.sync()
        self.accept()

    def _on_skip(self) -> None:
        self._config.onboarding_completed = True
        self._config.sync()
        self.accept()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()
