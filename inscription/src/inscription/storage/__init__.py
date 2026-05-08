"""Persistence layer: SQLite + filesystem.

This package is the only place that talks to ``sqlite3``. Higher layers use
:class:`SessionRepository` and receive/return :mod:`inscription.model`
domain objects.

The :mod:`inscription.storage.submitted` submodule tracks an
optional "submitted as evidence" marker file alongside the session
DB; the workspace UI reads it to show a banner and gate edits.
"""

from inscription.storage import submitted
from inscription.storage.errors import (
    SchemaVersionError,
    SessionAlreadyExistsError,
    SessionLockedError,
    SessionNotFoundError,
    StorageError,
)
from inscription.storage.repository import SessionRepository, list_sessions, slugify
from inscription.storage.submitted import SubmittedMarker

__all__ = [
    "SchemaVersionError",
    "SessionAlreadyExistsError",
    "SessionLockedError",
    "SessionNotFoundError",
    "SessionRepository",
    "StorageError",
    "SubmittedMarker",
    "list_sessions",
    "slugify",
    "submitted",
]
