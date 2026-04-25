"""Tiny reusable Qt builders for CaseForge.

Centralises a couple of small forms-and-dialogs idioms — the
``primary_tool`` combo box especially, since two screens (NewCaseDialog
and CaseView) need to render the same picker against the same
:data:`caseforge.model.PRIMARY_TOOL_CHOICES` list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QComboBox

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
