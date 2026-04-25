"""Tiny reusable Qt widget builders.

Inscription's UI uses a handful of recurring label shapes — small
bold "section" titles, muted hint text, etc. They were each spelled
out inline at every call site with hardcoded colour strings, which
made the palette inconsistent and theme changes painful. The QSS in
:mod:`inscription.ui.style` now styles ``[muted="true"]`` and
``[role="section-title"]`` selectors, and these helpers wire the
properties for callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def section_label(text: str, parent: QWidget | None = None) -> QLabel:
    """A small bold heading used to title editor / form sections."""
    label = QLabel(text, parent)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    label.setProperty("role", "section-title")
    return label


def muted_label(text: str, parent: QWidget | None = None, *, wrap: bool = True) -> QLabel:
    """A label rendered in the palette's muted text colour.

    Used for hints, secondary timestamps, and counts that should sit
    visually behind the primary content.
    """
    label = QLabel(text, parent)
    label.setProperty("muted", True)
    label.setWordWrap(wrap)
    return label
