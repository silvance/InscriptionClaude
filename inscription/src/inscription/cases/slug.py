"""Slug generation for case directory names.

Case numbers often contain characters that are fine in SQL but awkward on a
filesystem (slashes, colons, spaces). The slug is a filesystem-safe
representation of the case number used as the on-disk directory name.

The mapping is intentionally reversible-by-inspection: ``HSV-2026-0317``
stays ``HSV-2026-0317``; only unsafe characters get replaced.
"""

from __future__ import annotations

import re

# Characters we allow untouched in a slug. Everything else becomes '-'.
_SAFE = re.compile(r"[^A-Za-z0-9._-]")
_COLLAPSE = re.compile(r"-{2,}")


def slugify_case_number(case_number: str) -> str:
    """Return a filesystem-safe slug for ``case_number``.

    Rules:
        - Alphanumerics, ``.``, ``_``, and ``-`` pass through unchanged.
        - All other characters become a single ``-``.
        - Runs of ``-`` collapse to one.
        - Leading/trailing ``-`` are stripped.
        - Empty results raise ``ValueError`` — callers must validate input first.

    Args:
        case_number: The user-supplied case number.

    Returns:
        A filesystem-safe slug.

    Raises:
        ValueError: If the slug would be empty.
    """
    slug = _SAFE.sub("-", case_number.strip())
    slug = _COLLAPSE.sub("-", slug).strip("-")
    if not slug:
        msg = f"Case number {case_number!r} produces an empty slug"
        raise ValueError(msg)
    return slug
