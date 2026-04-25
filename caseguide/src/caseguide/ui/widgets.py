"""Tiny reusable Qt builders for CaseGuide.

Mirror of Inscription's / CaseForge's typography palette so the
three suite tools share a visual vocabulary. Each helper sets a
single ``role`` (or ``muted``) property that the QSS in
:mod:`caseguide.ui.style` styles, so theme tweaks flow from the
stylesheet and not from grep-replacing colour codes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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


def empty_state(
    *,
    title: str,
    body: str,
    cta_label: str | None = None,
    parent: QWidget | None = None,
) -> tuple[QWidget, QPushButton | None]:
    """A centered card with a title, supporting copy, and an optional CTA.

    Returns ``(container, cta_button)``. The button is ``None`` when
    ``cta_label`` is empty; otherwise the caller wires ``clicked``.
    """
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
