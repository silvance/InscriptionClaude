"""Windows UIA element resolver (``pywinauto`` backed).

The resolver queries the UIA tree at a given screen coordinate and reports
``name``, ``control_type``, ``automation_id``, and ``class_name`` with a
high confidence when it succeeds. If the immediate hit is anonymous --
common with WPF DataGrid cells, custom-painted widgets, and similar cases
where the user really clicked on the row/tab/button *containing* an
unnamed child -- the resolver walks up the UIA parent chain looking for
the nearest interactive ancestor with a name. If even that fails, it
delegates to the fallback resolver.

Import-time guard: :mod:`pywinauto` is optional and Windows-only. The module
imports lazily so non-Windows tests don't see it.
"""

from __future__ import annotations

import logging
from typing import Any

import psutil

from inscription.model import ResolvedElement
from inscription.resolve import ElementResolver

logger = logging.getLogger(__name__)


#: How far up the UIA tree to walk when the immediate hit is anonymous.
#: Eight is enough to cross a typical WPF DataGridCell -> DataGridRow ->
#: DataGrid -> TabItem chain without spending time on pathological
#: deep-nested layouts.
_MAX_WALK_UP_STEPS = 8

#: UIA control types that represent something the user can actually click
#: on with intent (vs containers, panes, and static decorations). When the
#: resolver walks up the tree it stops at the first ancestor in this set
#: that also carries a non-empty name. The list mirrors the UI Automation
#: ControlTypeId vocabulary.
_INTERACTIVE_CONTROL_TYPES: frozenset[str] = frozenset({
    "Button",
    "CheckBox",
    "ComboBox",
    "Edit",
    "Hyperlink",
    "ListItem",
    "MenuItem",
    "RadioButton",
    "SplitButton",
    "Tab",
    "TabItem",
    "ToolBar",
    "TreeItem",
})


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

        info, walk_steps = _walk_up_to_meaningful(info, max_steps=_MAX_WALK_UP_STEPS)

        name = _safe_get(info, "name") or _safe_get(info, "rich_text")
        control_type = _safe_get(info, "control_type")
        automation_id = _safe_get(info, "automation_id")
        class_name = _safe_get(info, "class_name")
        bounding_rect = _safe_rect(info)
        owner_process_name = _safe_process_name(info)

        if not any([name, control_type, automation_id, class_name]):
            return self._fallback.resolve_at(x, y)

        # Each step of walk-up means the user clicked on a child of the
        # named ancestor we're reporting. Subtract a touch of confidence
        # so step generation can prefer foreground-only fallback when the
        # walk got long.
        base = 0.9 if name and control_type else 0.6
        confidence = max(0.3, base - 0.05 * walk_steps)

        return ResolvedElement(
            id=None,
            name=name or None,
            control_type=control_type or None,
            automation_id=automation_id or None,
            class_name=class_name or None,
            role=control_type or None,
            confidence=confidence,
            method="uia" if walk_steps == 0 else "uia-walkup",
            bounding_rect=bounding_rect,
            owner_process_name=owner_process_name,
        )


def _walk_up_to_meaningful(info: Any, *, max_steps: int) -> tuple[Any, int]:
    """Climb the UIA parent chain until we find an interactive named element.

    Returns ``(info, steps_taken)``. ``steps_taken`` is 0 if the original
    element was already named-and-interactive, so the caller can tell the
    "exact hit" case apart from a walked-up one. Stops walking once an
    ancestor satisfies the criteria, once the parent chain runs out, or
    after ``max_steps`` -- whichever comes first.

    Pure helper -- takes any object with ``name`` / ``control_type`` /
    ``parent`` so tests can pass in a fake without dragging pywinauto into
    a Linux test environment.
    """
    if _is_meaningful(info):
        return info, 0
    current = info
    for step in range(1, max_steps + 1):
        try:
            parent = getattr(current, "parent", None)
        except Exception:
            return info, 0
        if parent is None or parent is current:
            return info, 0
        if _is_meaningful(parent):
            return parent, step
        current = parent
    return info, 0


def _is_meaningful(info: Any) -> bool:
    """An element is "meaningful" when it has a name *and* a control type
    we expect users to click on intentionally. Static labels (Text) and
    layout containers (Pane, Group, Custom) don't qualify even if named --
    a click on a label's text is almost always a positional accident.
    """
    name = _safe_get(info, "name")
    if not name:
        return False
    control_type = _safe_get(info, "control_type")
    return control_type in _INTERACTIVE_CONTROL_TYPES


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
