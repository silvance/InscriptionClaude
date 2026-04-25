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

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QComboBox, QFrame, QLabel

from caseforge.model import PRIMARY_TOOL_CHOICES

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


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
