"""Tiny reusable Qt builders for CaseGuide.

Mirror of Inscription's / CaseForge's typography palette so the
three suite tools share a visual vocabulary. Each helper sets a
single ``role`` (or ``muted``) property that the QSS in
:mod:`caseguide.ui.style` styles, so theme tweaks flow from the
stylesheet and not from grep-replacing colour codes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFrame, QLabel

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


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
    """A small chip label used for tags, priority levels, and inline status."""
    label = QLabel(text, parent)
    label.setProperty("role", role)
    return label


def horizontal_separator(parent: QWidget | None = None) -> QFrame:
    """One-pixel horizontal rule styled by the QSS."""
    rule = QFrame(parent)
    rule.setProperty("role", "separator")
    rule.setFrameShape(QFrame.Shape.NoFrame)
    return rule
