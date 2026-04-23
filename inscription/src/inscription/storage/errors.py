"""Exceptions raised by the storage layer."""

from __future__ import annotations


class StorageError(Exception):
    """Base class for all storage-layer errors."""


class SessionAlreadyExistsError(StorageError):
    """A session with this slug already exists in the workspace."""


class SessionNotFoundError(StorageError):
    """The requested session is not present in the workspace."""


class SessionLockedError(StorageError):
    """Another process (or a stale lockfile) is holding this session open."""


class SchemaVersionError(StorageError):
    """The session was created by a newer/incompatible version of Inscription."""
