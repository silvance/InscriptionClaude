"""Main application window.

Two-pane layout: scope on the left, suggestions on the right. A header
strip at the top carries the active-case badge and the primary action
buttons (Open, Generate, Save). The window remains usable when no case
is open — the panels show their empty states and Open is the only
enabled action.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from caseguide.config import Config
from caseguide.model import SuggestionsDocument, utcnow
from caseguide.ui.controller import CaseGuideController
from caseguide.ui.scope_panel import ScopePanel
from caseguide.ui.suggestions_panel import SuggestionsPanel
from caseguide.version import __version__

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent

    from caseguide.case_reader import CaseHandle

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level CaseGuide window."""

    def __init__(
        self,
        *,
        case_dir: Path | None = None,
        auto_show: bool = True,
    ) -> None:
        super().__init__()
        self._config = Config()
        self.setWindowTitle(f"CaseGuide {__version__}")
        self.resize(1200, 760)
        self._unsaved = False

        self._controller = CaseGuideController(parent_widget=self)
        self._controller.case_opened.connect(self._on_case_opened)
        self._controller.case_closed.connect(self._on_case_closed)
        self._controller.suggestions_loaded.connect(self._on_suggestions_loaded)

        self._scope = ScopePanel(self)
        self._suggestions = SuggestionsPanel(self)
        self._suggestions.changed.connect(self._on_suggestions_changed)

        self._header_label = self._build_header_label()
        self._open_btn, self._generate_btn, self._save_btn = self._build_action_buttons()

        self.setCentralWidget(self._build_central())
        self._build_menus()
        self.statusBar().showMessage("Ready")
        self._restore_geometry()

        if auto_show:
            self.show()
        if case_dir is not None:
            self._controller.open_existing(case_dir)

    def _build_header_label(self) -> QLabel:
        label = QLabel("No case open", self)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _build_action_buttons(self) -> tuple[QPushButton, QPushButton, QPushButton]:
        open_btn = QPushButton("Open case…", self)
        open_btn.clicked.connect(self._controller.open_from_picker)
        generate_btn = QPushButton("Generate suggestions", self)
        generate_btn.setProperty("role", "primary")
        generate_btn.clicked.connect(self._on_generate)
        generate_btn.setEnabled(False)
        save_btn = QPushButton("Save", self)
        save_btn.clicked.connect(self._on_save)
        save_btn.setEnabled(False)
        return open_btn, generate_btn, save_btn

    def _build_central(self) -> QWidget:
        header_row = QHBoxLayout()
        header_row.setContentsMargins(16, 12, 16, 12)
        header_row.setSpacing(10)
        header_row.addWidget(self._header_label, 1)
        header_row.addWidget(self._open_btn)
        header_row.addWidget(self._generate_btn)
        header_row.addWidget(self._save_btn)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._scope)
        splitter.addWidget(self._suggestions)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header_row)
        layout.addWidget(splitter, 1)
        return central

    # ------------------------------------------------------------ menus

    def _build_menus(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open case…", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._controller.open_from_picker)
        file_menu.addAction(open_action)

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        regenerate_action = QAction("&Generate suggestions", self)
        regenerate_action.setShortcut(QKeySequence("Ctrl+G"))
        regenerate_action.triggered.connect(self._on_generate)
        file_menu.addAction(regenerate_action)

        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About CaseGuide", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------ slots

    def _on_case_opened(self, handle: CaseHandle, case_dir: str) -> None:
        self._scope.show_case(handle, case_dir=case_dir)
        self.setWindowTitle(f"CaseGuide {__version__} — {handle.name}")
        self._header_label.setText(self._header_for(handle))
        self.statusBar().showMessage(f"Opened {case_dir}")
        self._generate_btn.setEnabled(True)

    def _on_case_closed(self) -> None:
        self._scope.clear()
        self._suggestions.set_suggestions([])
        self._header_label.setText("No case open")
        self.setWindowTitle(f"CaseGuide {__version__}")
        self._generate_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._unsaved = False

    def _on_suggestions_loaded(self, doc: SuggestionsDocument | None) -> None:
        if doc is None:
            self._suggestions.set_suggestions([])
            self.statusBar().showMessage(
                "No saved suggestions — click Generate to draft a list."
            )
            self._save_btn.setEnabled(False)
            self._unsaved = False
            return
        self._suggestions.set_suggestions(doc.suggestions)
        when = doc.generated_at.astimezone().strftime("%Y-%m-%d %H:%M")
        self.statusBar().showMessage(
            f"Loaded {len(doc.suggestions)} suggestion(s) · last generated {when}"
        )
        # Loading from disk doesn't dirty the buffer; but enable Save so
        # the user can re-save if they want to bump the timestamp.
        self._save_btn.setEnabled(True)
        self._unsaved = False

    def _on_suggestions_changed(self) -> None:
        self._unsaved = True
        self._save_btn.setEnabled(self._controller.current_case_dir() is not None)

    def _on_generate(self) -> None:
        doc = self._controller.generate()
        if doc is None:
            return
        self._suggestions.set_suggestions(doc.suggestions)
        ids = ", ".join(doc.playbooks) if doc.playbooks else "—"
        self.statusBar().showMessage(
            f"Generated {len(doc.suggestions)} suggestion(s) from playbooks: {ids}"
        )
        self._unsaved = True
        self._save_btn.setEnabled(True)

    def _on_save(self) -> None:
        case_dir = self._controller.current_case_dir()
        if case_dir is None:
            return
        doc = SuggestionsDocument(
            generated_at=utcnow(),
            scope_summary=self._scope_summary_for_save(),
            suggestions=self._suggestions.suggestions(),
        )
        if self._controller.save(doc):
            self.statusBar().showMessage("Saved suggestions.json.")
            self._unsaved = False

    def _scope_summary_for_save(self) -> str:
        case = self._controller.current_case()
        if case is None:
            return ""
        scope = case.scope
        bits: list[str] = []
        if scope.exam_type:
            bits.append(scope.exam_type)
        if scope.primary_tool:
            bits.append(f"tool: {scope.primary_tool}")
        if scope.device_classes:
            bits.append("devices: " + ", ".join(scope.device_classes))
        return " · ".join(bits) if bits else (scope.summary[:200] if scope.summary else "")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About CaseGuide",
            (
                f"<h3>CaseGuide {__version__}</h3>"
                "<p>LLM-assisted exam coach for the Inscription "
                "forensic-exam suite.</p>"
            ),
        )

    @staticmethod
    def _header_for(handle: CaseHandle) -> str:
        ref = f" · {handle.case_reference}" if handle.case_reference else ""
        tool = (
            f" · tool: {handle.scope.primary_tool}"
            if handle.scope.primary_tool
            else ""
        )
        return f"{handle.name}{ref}{tool}"

    # -------------------------------------------------------- geometry

    def _restore_geometry(self) -> None:
        geom = self._config.window_geometry
        if geom is not None:
            self.restoreGeometry(geom)
        state = self._config.window_state
        if state is not None:
            self.restoreState(state)

    def _save_geometry(self) -> None:
        self._config.window_geometry = self.saveGeometry()
        self._config.window_state = self.saveState()
        self._config.sync()

    # -------------------------------------------------------- events

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._unsaved:
            reply = QMessageBox.question(
                self,
                "Unsaved suggestions",
                "Save changes to suggestions.json before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
        self._save_geometry()
        super().closeEvent(event)
