"""JSON-tolerant coercion helpers used by every app that reads case.json,
suggestions.json, or manifest.json. Each returns a sensible default when
the input is missing, the wrong type, or unparseable — case files we
read may have been written by an older or partially-corrupted install.
"""

from __future__ import annotations

from datetime import datetime


def coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def coerce_bool(value: object, *, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def parse_iso(value: object, *, default: datetime | None) -> datetime | None:
    """Parse an ISO 8601 timestamp; return ``default`` if absent or invalid.

    Callers pick the fallback explicitly: a real ``datetime`` for fields
    that need *some* timestamp; ``None`` for optional fields.
    """
    if not isinstance(value, str) or not value:
        return default
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return default


def parse_optional_iso(value: object) -> datetime | None:
    """Convenience wrapper for ``parse_iso(value, default=None)``."""
    return parse_iso(value, default=None)


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
