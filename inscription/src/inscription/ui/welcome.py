"""The "no session open" landing page.

Shown by :class:`MainWindow` when nothing is open. Replaces what used to
be a bare centred ``QLabel("No session open")`` with a small welcome
card: app name, tagline, primary "Open Session…" call to action, and a
list of recent sessions on the same workspace so the user can jump
straight back into yesterday's work.

The widget never holds a repository handle; it pulls a thin recent-list
from :func:`inscription.storage.list_sessions` on demand and emits
signals the controller listens on.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from inscription.storage import list_sessions
from inscription.version import __version__

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

#: How many of the most-recent sessions to surface on the welcome page.
_RECENT_LIMIT = 6


class WelcomePage(QWidget):
    """Empty-state welcome with a primary CTA and a recent-sessions list."""

    open_session_requested = Signal()
    open_existing_requested = Signal(str)  # slug

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.addStretch(1)

        card = QFrame(self)
        card.setProperty("role", "card")
        card.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        card.setMaximumWidth(560)
        card.setMinimumWidth(420)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(14)

        title = QLabel("Inscription", card)
        title_font = title.font()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        subtitle = QLabel(
            f"Version {__version__} — record a Windows workflow, "
            "auto-generate an editable guide.",
            card,
        )
        subtitle.setStyleSheet("color: #6e6e73;")
        subtitle.setWordWrap(True)

        cta = QPushButton("Open Session…", card)
        cta.setProperty("role", "primary")
        cta.setMinimumHeight(36)
        cta.setMinimumWidth(160)
        cta.clicked.connect(self.open_session_requested)

        cta_row = QHBoxLayout()
        cta_row.addWidget(cta)
        cta_row.addStretch(1)

        recent_heading = QLabel("Recent sessions", card)
        recent_font = recent_heading.font()
        recent_font.setBold(True)
        recent_heading.setFont(recent_font)
        recent_heading.setStyleSheet("margin-top: 8px;")

        self._recent_list = QListWidget(card)
        self._recent_list.setMinimumHeight(180)
        self._recent_list.itemActivated.connect(self._on_activated)

        self._empty_label = QLabel("No sessions yet — start one above.", card)
        self._empty_label.setStyleSheet("color: #6e6e73; padding: 8px;")
        self._empty_label.setVisible(False)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(cta_row)
        card_layout.addSpacing(8)
        card_layout.addWidget(recent_heading)
        card_layout.addWidget(self._recent_list, 1)
        card_layout.addWidget(self._empty_label)

        outer.addWidget(card, 1)
        outer.addStretch(1)

    # ----------------------------------------------------------- API

    def refresh(self, workspace_root: Path) -> None:
        """Reload the recent-sessions list from ``workspace_root``."""
        self._recent_list.clear()
        try:
            sessions = list_sessions(workspace_root)
        except Exception:
            logger.exception("WelcomePage: list_sessions failed")
            sessions = []

        # Sort newest-first by started_at, then take the top N.
        sessions = sorted(
            sessions, key=lambda pair: pair[1].started_at, reverse=True
        )[:_RECENT_LIMIT]

        if not sessions:
            self._recent_list.setVisible(False)
            self._empty_label.setVisible(True)
            return

        self._recent_list.setVisible(True)
        self._empty_label.setVisible(False)
        for slug, manifest in sessions:
            started = manifest.started_at.strftime("%Y-%m-%d %H:%M")
            label = (
                f"{manifest.name}\n"
                f"{started} · {manifest.step_count} step"
                f"{'s' if manifest.step_count != 1 else ''}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, slug)
            self._recent_list.addItem(item)

    # -------------------------------------------------------- internals

    def _on_activated(self, item: QListWidgetItem) -> None:
        slug = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(slug, str):
            self.open_existing_requested.emit(slug)
