"""Application-wide visual styling.

CaseGuide mirrors Inscription's visual language so the two apps in
the suite read as siblings: Segoe UI typography, a subdued neutral
palette, accent blue for primary actions. The stylesheet is applied
once via :func:`apply_global_style` from the app bootstrap.

The two styles are kept as parallel copies (rather than a shared
package) for now — each tool stays a self-contained PyInstaller build
with no cross-tool import. If divergence becomes painful we'll factor
into a shared ``forensic_suite_style`` package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


@dataclass(frozen=True, slots=True)
class Palette:
    """The set of colours the stylesheets paint with."""

    bg: str
    surface: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_text: str
    danger: str
    danger_hover: str


LIGHT = Palette(
    bg="#f5f5f7",
    surface="#ffffff",
    surface_hover="#f0f0f5",
    border="#e5e5e7",
    border_strong="#d2d2d7",
    text="#1d1d1f",
    text_muted="#6e6e73",
    accent="#0066cc",
    accent_hover="#0052a3",
    accent_text="#ffffff",
    danger="#d70015",
    danger_hover="#a30010",
)

DARK = Palette(
    bg="#1d1d1f",
    surface="#2c2c2e",
    surface_hover="#3a3a3c",
    border="#3a3a3c",
    border_strong="#48484a",
    text="#f2f2f7",
    text_muted="#98989d",
    accent="#0a84ff",
    accent_hover="#3395ff",
    accent_text="#ffffff",
    danger="#ff453a",
    danger_hover="#ff6961",
)

#: Body type stack. Segoe UI on Windows; the fallbacks cover macOS / Linux
#: development.
FONT_STACK = '"Segoe UI", "SF Pro Text", "Helvetica Neue", Roboto, Arial, sans-serif'

#: Width of the QListWidget / QTextEdit content border. Kept thin so the
#: surrounding card-like grouping reads as the structural element.
BORDER_PX = 1


def detect_palette(app: QApplication | None = None) -> Palette:
    """Pick the light or dark palette to match the OS colour scheme."""
    hints = QGuiApplication.styleHints()
    try:
        scheme = hints.colorScheme()
    except AttributeError:  # pragma: no cover - older Qt
        return LIGHT
    if scheme == Qt.ColorScheme.Dark:
        return DARK
    return LIGHT


def apply_global_style(app: QApplication) -> Palette:
    """Apply the chosen palette's stylesheet to ``app``. Returns the palette
    so callers can use it for any widget-local accents (e.g. a recording
    indicator)."""
    palette = detect_palette(app)
    app.setStyleSheet(_qss(palette))
    return palette


def _qss(p: Palette) -> str:
    """Build the application stylesheet from a palette."""
    return f"""
* {{
    font-family: {FONT_STACK};
    font-size: 13px;
}}

QMainWindow, QDialog, QWidget {{
    background-color: {p.bg};
    color: {p.text};
}}

QLabel {{
    background: transparent;
    color: {p.text};
}}

*[role="card"] {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border};
    border-radius: 8px;
}}

QLabel[role="card"] {{
    color: {p.text_muted};
    qproperty-alignment: AlignCenter;
    padding: 12px;
}}

/* ------------------------------------------------------------ buttons */

QPushButton {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border_strong};
    border-radius: 6px;
    padding: 6px 14px;
    color: {p.text};
}}

QPushButton:hover {{
    background-color: {p.surface_hover};
}}

QPushButton:pressed {{
    background-color: {p.border};
}}

QPushButton:disabled {{
    color: {p.text_muted};
    background-color: {p.bg};
    border-color: {p.border};
}}

QPushButton[role="primary"] {{
    background-color: {p.accent};
    color: {p.accent_text};
    border-color: {p.accent};
    font-weight: 600;
}}

QPushButton[role="primary"]:hover {{
    background-color: {p.accent_hover};
    border-color: {p.accent_hover};
}}

QPushButton[role="primary"]:disabled {{
    background-color: {p.border_strong};
    color: {p.text_muted};
    border-color: {p.border_strong};
}}

QPushButton[role="danger"] {{
    background-color: {p.danger};
    color: white;
    border-color: {p.danger};
    font-weight: 600;
}}

QPushButton[role="danger"]:hover {{
    background-color: {p.danger_hover};
    border-color: {p.danger_hover};
}}

/* ------------------------------------------------------------- inputs */

QLineEdit, QTextEdit {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border_strong};
    border-radius: 6px;
    padding: 6px 10px;
    color: {p.text};
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}

QLineEdit:focus, QTextEdit:focus {{
    border-color: {p.accent};
}}

QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {p.bg};
    color: {p.text_muted};
}}

QCheckBox {{
    spacing: 8px;
    color: {p.text};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: {BORDER_PX}px solid {p.border_strong};
    border-radius: 4px;
    background: {p.surface};
}}

QCheckBox::indicator:hover {{
    border-color: {p.accent};
}}

QCheckBox::indicator:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
}}

/* -------------------------------------------------------------- lists */

QListWidget {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border};
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    color: {p.text};
}}

QListWidget::item {{
    padding: 8px 8px;
    border-radius: 4px;
    margin: 1px 0;
}}

QListWidget::item:hover {{
    background-color: {p.surface_hover};
}}

QListWidget::item:selected {{
    background-color: {p.accent};
    color: {p.accent_text};
}}

/* ---------------------------------------------------------- chrome */

QMenuBar {{
    background-color: {p.bg};
    color: {p.text};
    border-bottom: {BORDER_PX}px solid {p.border};
}}

QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
}}

QMenuBar::item:selected {{
    background-color: {p.surface_hover};
    border-radius: 4px;
}}

QMenu {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border_strong};
    border-radius: 6px;
    padding: 4px;
    color: {p.text};
}}

QMenu::item {{
    padding: 6px 24px 6px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {p.accent};
    color: {p.accent_text};
}}

QMenu::separator {{
    background-color: {p.border};
    height: 1px;
    margin: 4px 8px;
}}

QStatusBar {{
    background-color: {p.bg};
    color: {p.text_muted};
    border-top: {BORDER_PX}px solid {p.border};
}}

QStatusBar::item {{
    border: 0;
}}

QSplitter::handle {{
    background-color: {p.border};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* ----------------------------------------------------------- scrollbars */

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {p.border_strong};
    border-radius: 5px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.text_muted};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {p.border_strong};
    border-radius: 5px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {p.text_muted};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

QProgressBar {{
    background-color: {p.bg};
    border: {BORDER_PX}px solid {p.border};
    border-radius: 4px;
    text-align: center;
    color: {p.text};
    height: 8px;
}}

QProgressBar::chunk {{
    background-color: {p.accent};
    border-radius: 3px;
}}

QToolTip {{
    background-color: {p.text};
    color: {p.bg};
    border: 0;
    padding: 4px 8px;
    border-radius: 4px;
}}
"""
