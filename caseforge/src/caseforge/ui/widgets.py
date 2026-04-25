"""Tiny reusable Qt builders for CaseForge.

Two clusters of helpers:

- The primary-tool combo box — used by both NewCaseDialog and
  CaseView so the picker stays consistent against
  :data:`caseforge.model.PRIMARY_TOOL_CHOICES`.
- A typography / chip palette (display title, section heading,
  muted text, caption, badge) backed by QSS role properties in
  :mod:`caseforge.ui.style`. Mirrors Inscription's and CaseGuide's
  helpers so the three suite tools share a visual vocabulary.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from caseforge.model import PRIMARY_TOOL_CHOICES


def build_primary_tool_combo(parent: QWidget | None = None) -> QComboBox:
    """Combo box pre-populated with the primary-tool choices.

    Items carry the stable id (e.g. ``"axiom"``) as ``itemData`` so
    callers store the id, not the display label, which keeps the
    on-disk vocabulary consistent across UI tweaks.
    """
    combo = QComboBox(parent)
    for value, label in PRIMARY_TOOL_CHOICES:
        combo.addItem(label, value)
    return combo


def select_primary_tool(combo: QComboBox, value: str) -> None:
    """Set the combo to the entry whose stable id matches ``value``."""
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            combo.setCurrentIndex(index)
            return
    # Unknown id — keep selection where it is rather than guessing.


def primary_tool_value(combo: QComboBox) -> str:
    """Return the stable id of the currently-selected primary tool."""
    data = combo.currentData()
    return str(data) if data is not None else ""


# -------------------------------------------------------- typography


def display_label(text: str, parent: QWidget | None = None) -> QLabel:
    """The largest text on a page — the page or pane title."""
    label = QLabel(text, parent)
    label.setProperty("role", "display-title")
    return label


def page_subtitle(text: str, parent: QWidget | None = None, *, wrap: bool = True) -> QLabel:
    """One-line muted subtitle that sits under a display-title."""
    label = QLabel(text, parent)
    label.setProperty("role", "page-subtitle")
    label.setWordWrap(wrap)
    return label


def section_label(text: str, parent: QWidget | None = None) -> QLabel:
    """A small uppercase heading used to title editor / form sections."""
    label = QLabel(text, parent)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    label.setProperty("role", "section-title")
    return label


def muted_label(text: str, parent: QWidget | None = None, *, wrap: bool = True) -> QLabel:
    """A label rendered in the palette's muted text colour."""
    label = QLabel(text, parent)
    label.setProperty("muted", "true")
    label.setWordWrap(wrap)
    return label


def caption_label(text: str, parent: QWidget | None = None, *, wrap: bool = True) -> QLabel:
    """Smaller-than-body muted text — captions, timestamps, footnotes."""
    label = QLabel(text, parent)
    label.setProperty("role", "caption")
    label.setWordWrap(wrap)
    return label


def badge_label(
    text: str,
    parent: QWidget | None = None,
    *,
    role: str = "badge",
) -> QLabel:
    """A small chip label used for tags and inline status."""
    label = QLabel(text, parent)
    label.setProperty("role", role)
    return label


def horizontal_separator(parent: QWidget | None = None) -> QFrame:
    """One-pixel horizontal rule styled by the QSS."""
    rule = QFrame(parent)
    rule.setProperty("role", "separator")
    rule.setFrameShape(QFrame.Shape.NoFrame)
    return rule


def empty_state(
    *,
    title: str,
    body: str,
    cta_label: str | None = None,
    parent: QWidget | None = None,
) -> tuple[QWidget, QPushButton | None]:
    """Centered card with title + supporting copy + optional primary CTA."""
    card = QFrame(parent)
    card.setProperty("role", "card")
    card.setMaximumWidth(540)
    card.setMinimumWidth(360)

    title_label = QLabel(title, card)
    title_label.setProperty("role", "display-title")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    body_label = QLabel(body, card)
    body_label.setProperty("muted", "true")
    body_label.setWordWrap(True)
    body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    cta: QPushButton | None = None
    layout = QVBoxLayout(card)
    layout.setContentsMargins(36, 36, 36, 36)
    layout.setSpacing(10)
    layout.addStretch(1)
    layout.addWidget(title_label)
    layout.addWidget(body_label)
    if cta_label:
        cta = QPushButton(cta_label, card)
        cta.setProperty("role", "primary")
        cta.setMinimumHeight(36)
        cta.setMinimumWidth(180)
        cta_row = QHBoxLayout()
        cta_row.addStretch(1)
        cta_row.addWidget(cta)
        cta_row.addStretch(1)
        layout.addSpacing(6)
        layout.addLayout(cta_row)
    layout.addStretch(2)

    container = QWidget(parent)
    outer = QHBoxLayout(container)
    outer.addStretch(1)
    outer.addWidget(card)
    outer.addStretch(1)
    return container, cta
