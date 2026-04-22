"""Exceptions raised by the storage layer."""

from __future__ import annotations


class StorageError(Exception):
    """Base class for all storage-layer errors."""


class CaseAlreadyExistsError(StorageError):
    """A case with this number already exists in the workspace."""


class CaseNotFoundError(StorageError):
    """The requested case is not present in the workspace."""


class CaseLockedError(StorageError):
    """Another process (or a stale lockfile) is holding this case open."""


class SchemaVersionError(StorageError):
    """The case was created by a newer/incompatible version of Inscription."""
