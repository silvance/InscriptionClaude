"""Slug generation for session directory names.

Session names are free-form (``"Reset AWS password"``). The slug is a
filesystem-safe representation used as the on-disk directory name. Uniqueness
across existing slugs is the caller's concern — :class:`SessionRepository`
handles collision by raising when the target directory already exists.
"""

from __future__ import annotations

import re

_SAFE = re.compile(r"[^A-Za-z0-9._-]")
_COLLAPSE = re.compile(r"-{2,}")


def slugify(name: str) -> str:
    """Return a filesystem-safe slug for ``name``.

    Rules:
        - Alphanumerics, ``.``, ``_``, and ``-`` pass through unchanged.
        - All other characters become ``-``.
        - Runs of ``-`` collapse to one.
        - Leading/trailing ``-`` are stripped.
        - Empty results raise ``ValueError``.
    """
    slug = _SAFE.sub("-", name.strip())
    slug = _COLLAPSE.sub("-", slug).strip("-")
    if not slug:
        msg = f"Name {name!r} produces an empty slug"
        raise ValueError(msg)
    return slug
