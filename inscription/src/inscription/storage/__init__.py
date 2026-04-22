"""Persistence layer: SQLite + filesystem.

This package is the only place that talks to ``sqlite3``. Higher layers use
:class:`CaseRepository` and receive/return :mod:`inscription.cases` domain
objects.
"""

from inscription.storage.errors import (
    CaseAlreadyExistsError,
    CaseLockedError,
    CaseNotFoundError,
    SchemaVersionError,
    StorageError,
)
from inscription.storage.repository import CaseRepository

__all__ = [
    "CaseAlreadyExistsError",
    "CaseLockedError",
    "CaseNotFoundError",
    "CaseRepository",
    "SchemaVersionError",
    "StorageError",
]
