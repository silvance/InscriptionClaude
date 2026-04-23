"""Element resolver interfaces and fallback implementations.

UIA-backed resolution lives in :mod:`inscription.resolve.uia` (Windows only).
The fallbacks in this module work on any platform so the rest of the
pipeline stays testable without a display server.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from inscription.model import ResolvedElement

if TYPE_CHECKING:
    from inscription.platform import ForegroundInfo, ForegroundInspector

logger = logging.getLogger(__name__)


class ElementResolver(ABC):
    """Return a :class:`ResolvedElement` for a screen coordinate."""

    @abstractmethod
    def resolve_at(self, x: int, y: int) -> ResolvedElement:
        """Return the best-effort resolution at ``(x, y)``."""


class NullResolver(ElementResolver):
    """Returns a zero-confidence placeholder. Used when nothing better exists."""

    def resolve_at(self, x: int, y: int) -> ResolvedElement:
        return ResolvedElement(id=None, confidence=0.0, method="none")


class ForegroundFallbackResolver(ElementResolver):
    """Resolve using only foreground window metadata.

    No knowledge of the clicked element itself — just which window/process
    was in focus. Confidence is intentionally low so step generation can
    produce more generic text ("Click in Notepad") instead of fabricating
    a control name.
    """

    def __init__(self, inspector: ForegroundInspector) -> None:
        self._inspector = inspector

    def resolve_at(self, x: int, y: int) -> ResolvedElement:
        fg: ForegroundInfo = self._inspector.inspect()
        if not fg.window_title and not fg.process_name:
            return ResolvedElement(id=None, confidence=0.0, method="none")
        return ResolvedElement(
            id=None,
            name=fg.window_title or None,
            control_type=None,
            automation_id=None,
            class_name=fg.process_name or None,
            role="window",
            confidence=0.3,
            method="foreground-only",
        )


def create_element_resolver(inspector: ForegroundInspector) -> ElementResolver:
    """Return the best resolver available on the current platform.

    Order of preference:

    1. ``UiaElementResolver`` (Windows + ``pywinauto`` present)
    2. ``ForegroundFallbackResolver`` (any platform with a foreground inspector)
    """
    if os.name == "nt":
        try:
            from inscription.resolve.uia import UiaElementResolver  # noqa: PLC0415

            return UiaElementResolver(fallback=ForegroundFallbackResolver(inspector))
        except Exception as exc:  # pragma: no cover - runtime import-only path
            logger.info("UIA resolver unavailable (%s); using foreground-only", exc)
    return ForegroundFallbackResolver(inspector)
