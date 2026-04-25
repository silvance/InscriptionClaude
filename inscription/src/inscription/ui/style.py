"""Application-wide visual styling.

Inscription targets a clean, native-feeling Windows look: Segoe UI
typography, a subdued neutral palette, accent blue for primary actions,
and red reserved for destructive / recording state. Light and dark
variants are picked from the system colour scheme on application
start.

The stylesheet is applied once via :func:`apply_global_style` from the
app bootstrap. Individual widgets shouldn't set their own
``setStyleSheet`` for things this file already covers — global control
is what makes the app feel coherent rather than slapped together.
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

/* ------------------------------------------------------------ labels */

QLabel {{
    background: transparent;
    color: {p.text};
}}

QLabel[muted="true"] {{
    color: {p.text_muted};
}}

QLabel[role="section-title"] {{
    color: {p.text_muted};
    letter-spacing: 0.4px;
    text-transform: uppercase;
    font-size: 11px;
}}

QLabel[role="display-title"] {{
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.01em;
}}

QLabel[role="page-subtitle"] {{
    color: {p.text_muted};
    font-size: 13px;
}}

QLabel[role="caption"] {{
    color: {p.text_muted};
    font-size: 11px;
}}

QLabel[role="badge"] {{
    background: {p.surface_hover};
    color: {p.text_muted};
    border: {BORDER_PX}px solid {p.border};
    border-radius: 10px;
    padding: 1px 8px;
    font-size: 11px;
}}

QLabel[role="badge-accent"] {{
    background: {p.accent};
    color: {p.accent_text};
    border-radius: 10px;
    padding: 1px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel[role="badge-danger"] {{
    background: {p.danger};
    color: white;
    border-radius: 10px;
    padding: 1px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* ----------------------------------------------------------- surfaces */

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

*[role="page-header"] {{
    background-color: {p.surface};
    border-bottom: {BORDER_PX}px solid {p.border};
}}

QFrame[role="separator"] {{
    background: {p.border};
    max-height: 1px;
    min-height: 1px;
    border: 0;
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
    border-color: {p.text_muted};
}}

QPushButton:pressed {{
    background-color: {p.border};
}}

QPushButton:focus {{
    border-color: {p.accent};
    outline: 0;
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

QPushButton[role="primary"]:pressed {{
    background-color: {p.accent_hover};
    border-color: {p.accent_hover};
}}

QPushButton[role="primary"]:focus {{
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

QPushButton[role="ghost"] {{
    background: transparent;
    border: 0;
    color: {p.text_muted};
    padding: 4px 8px;
}}

QPushButton[role="ghost"]:hover {{
    background-color: {p.surface_hover};
    color: {p.text};
}}

QToolButton {{
    background: transparent;
    border: 0;
    border-radius: 4px;
    padding: 4px 8px;
    color: {p.text};
}}

QToolButton:hover {{
    background-color: {p.surface_hover};
}}

QToolButton:pressed {{
    background-color: {p.border};
}}

/* ------------------------------------------------------------- inputs */

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border_strong};
    border-radius: 6px;
    padding: 6px 10px;
    color: {p.text};
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
    border-color: {p.accent};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {p.bg};
    color: {p.text_muted};
}}

QComboBox {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border_strong};
    border-radius: 6px;
    padding: 5px 10px;
    color: {p.text};
    min-width: 120px;
}}

QComboBox:hover {{
    border-color: {p.text_muted};
}}

QComboBox:focus {{
    border-color: {p.accent};
}}

QComboBox::drop-down {{
    border: 0;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {p.surface};
    border: {BORDER_PX}px solid {p.border_strong};
    border-radius: 6px;
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
    padding: 4px;
    outline: 0;
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

/* ----------------------------------------------------------- form layout */

QGroupBox {{
    border: {BORDER_PX}px solid {p.border};
    border-radius: 8px;
    margin-top: 14px;
    padding: 18px 14px 12px 14px;
    background-color: {p.surface};
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {p.text_muted};
    background: {p.bg};
    margin-left: 8px;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.4px;
}}

/* -------------------------------------------------------------- tabs */

QTabWidget::pane {{
    border: 0;
    background: transparent;
    padding-top: 6px;
}}

QTabBar {{
    qproperty-drawBase: 0;
    background: transparent;
}}

QTabBar::tab {{
    background: transparent;
    border: 0;
    color: {p.text_muted};
    padding: 8px 14px;
    margin-right: 4px;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}

QTabBar::tab:hover {{
    color: {p.text};
}}

QTabBar::tab:selected {{
    color: {p.text};
    border-bottom-color: {p.accent};
}}

QTabBar::tab:disabled {{
    color: {p.border_strong};
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
    padding: 8px 10px;
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

QListWidget::item:selected:!active {{
    background-color: {p.surface_hover};
    color: {p.text};
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
    padding: 2px 8px;
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
