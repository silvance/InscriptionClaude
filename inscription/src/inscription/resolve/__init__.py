"""UI element resolution.

Given a screen coordinate, a resolver returns a :class:`ResolvedElement`
describing what the user clicked. The best-effort hierarchy is:

- ``UiaElementResolver`` — Windows UIA via ``pywinauto``. High confidence
  (~0.9) when successful; reports control type, name, automation id.
- ``ForegroundFallbackResolver`` — when UIA is unavailable, fall back to
  the foreground window's title and process name. Low confidence (~0.3).
- ``NullResolver`` — returns a zero-confidence placeholder.

:func:`create_element_resolver` picks the best available at runtime.
"""

from inscription.resolve.base import (
    ElementResolver,
    ForegroundFallbackResolver,
    NullResolver,
    create_element_resolver,
)

__all__ = [
    "ElementResolver",
    "ForegroundFallbackResolver",
    "NullResolver",
    "create_element_resolver",
]
