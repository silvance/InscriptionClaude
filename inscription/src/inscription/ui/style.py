"""Re-export the shared suite stylesheet.

The actual QSS body, palette, and ``apply_global_style`` helper live
in :mod:`suite_common.ui.style` so all three suite apps render
identically. Imports of ``apply_global_style`` (or ``Palette`` /
``LIGHT`` / ``DARK`` for the app-icon builder) from
``inscription.ui.style`` keep working unchanged.
"""

from suite_common.ui.style import (
    BORDER_PX,
    DARK,
    FONT_STACK,
    LIGHT,
    Palette,
    apply_global_style,
    detect_palette,
)

__all__ = [
    "BORDER_PX",
    "DARK",
    "FONT_STACK",
    "LIGHT",
    "Palette",
    "apply_global_style",
    "detect_palette",
]
