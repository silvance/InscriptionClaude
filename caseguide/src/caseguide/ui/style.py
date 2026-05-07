"""Re-export the shared suite stylesheet.

CaseGuide mirrors Inscription's visual language so the suite reads
as siblings; the QSS body lives in :mod:`suite_common.ui.style`
and is shared by all three apps. Imports from
``caseguide.ui.style`` keep working unchanged.
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
