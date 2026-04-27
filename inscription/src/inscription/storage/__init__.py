"""Persistence layer: SQLite + filesystem.

This package is the only place that talks to ``sqlite3``. Higher layers use
:class:`SessionRepository` and receive/return :mod:`inscription.model`
domain objects.
"""

from inscription.storage.errors import (
    SchemaVersionError,
    SessionAlreadyExistsError,
    SessionLockedError,
    SessionNotFoundError,
    StorageError,
)
from inscription.storage.repository import SessionRepository, list_sessions, slugify

__all__ = [
    "SchemaVersionError",
    "SessionAlreadyExistsError",
    "SessionLockedError",
    "SessionNotFoundError",
    "SessionRepository",
    "StorageError",
    "list_sessions",
    "slugify",
]
