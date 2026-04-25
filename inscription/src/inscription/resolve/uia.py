"""Windows UIA element resolver (``pywinauto`` backed).

The resolver queries the UIA tree at a given screen coordinate and reports
``name``, ``control_type``, ``automation_id``, and ``class_name`` with a
high confidence when it succeeds. If UIA cannot resolve the point — which
happens with custom-painted widgets, web content without accessibility
flags, and some elevated processes — it delegates to the fallback resolver.

Import-time guard: :mod:`pywinauto` is optional and Windows-only. The module
imports lazily so non-Windows tests don't see it.
"""

from __future__ import annotations

import logging
from typing import Any

import psutil

from inscription.model import ResolvedElement
from inscription.resolve.base import ElementResolver

logger = logging.getLogger(__name__)


class UiaElementResolver(ElementResolver):
    """Resolve UI elements via pywinauto's UIA backend."""

    def __init__(self, *, fallback: ElementResolver) -> None:
        # Import at construction time so unrelated platforms never touch it.
        from pywinauto.uia_element_info import UIAElementInfo  # noqa: PLC0415

        self._UIAElementInfo = UIAElementInfo
        self._fallback = fallback

    def resolve_at(self, x: int, y: int) -> ResolvedElement:
        try:
            info: Any = self._UIAElementInfo.from_point(x, y)
        except Exception as exc:
            logger.debug("UIA resolve failed at (%d,%d): %s", x, y, exc)
            return self._fallback.resolve_at(x, y)
        if info is None:
            return self._fallback.resolve_at(x, y)

        name = _safe_get(info, "name") or _safe_get(info, "rich_text")
        control_type = _safe_get(info, "control_type")
        automation_id = _safe_get(info, "automation_id")
        class_name = _safe_get(info, "class_name")
        bounding_rect = _safe_rect(info)
        owner_process_name = _safe_process_name(info)

        if not any([name, control_type, automation_id, class_name]):
            return self._fallback.resolve_at(x, y)

        return ResolvedElement(
            id=None,
            name=name or None,
            control_type=control_type or None,
            automation_id=automation_id or None,
            class_name=class_name or None,
            role=control_type or None,
            confidence=0.9 if name and control_type else 0.6,
            method="uia",
            bounding_rect=bounding_rect,
            owner_process_name=owner_process_name,
        )


def _safe_get(info: Any, attr: str) -> str:
    try:
        value = getattr(info, attr, None)
    except Exception:
        return ""
    if value is None:
        return ""
    return str(value).strip()


def _safe_process_name(info: Any) -> str | None:
    """Return the executable name for the process that owns ``info``.

    Used by step generation to tell apart "clicked a button inside the
    foreground app" from "clicked the taskbar / Start menu / Alt-Tab
    switcher, which lives in explorer.exe". Returns ``None`` if UIA
    didn't surface a process id or the process is no longer around.
    """
    try:
        pid = getattr(info, "process_id", None)
    except Exception:
        return None
    if not pid:
        return None
    try:
        name = psutil.Process(int(pid)).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
        return None
    return str(name) if name else None


def _safe_rect(info: Any) -> tuple[int, int, int, int] | None:
    """Extract the element's screen-space bounding rectangle.

    pywinauto's ``UIAElementInfo.rectangle`` returns a ``RECT`` with
    ``.left/.top/.right/.bottom``. Returns ``None`` if anything in that
    read fails or the rect is empty.
    """
    try:
        rect = getattr(info, "rectangle", None)
    except Exception:
        return None
    if rect is None:
        return None
    try:
        left = int(rect.left)
        top = int(rect.top)
        right = int(rect.right)
        bottom = int(rect.bottom)
    except (AttributeError, TypeError, ValueError):
        return None
    if right <= left or bottom <= top:
        return None
    return (left, top, right, bottom)
