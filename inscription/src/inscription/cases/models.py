"""Domain model dataclasses for cases, sessions, and steps.

These are immutable value objects. Mutations happen through the repository;
this layer stays pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


#: Schema version written into every new case. Bumped when the SQLite schema
#: changes in a way that requires migration.
SCHEMA_VERSION = 1


class StepKind(StrEnum):
    """Classification of a step's origin."""

    HOTKEY_CAPTURE = "hotkey_capture"
    MANUAL_NOTE = "manual_note"
    AUTO_CAPTURE = "auto_capture"  # Phase 4, kept here so the enum is stable
    PROMOTED_BUFFER = "promoted_buffer"  # Phase 4


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware ``datetime``."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseInfo:
    """Top-level case metadata. One instance per case."""

    case_number: str
    title: str
    examiner: str
    agency: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True, kw_only=True)
class Session:
    """A capture session within a case.

    Phase 1 auto-creates one session per case-open. Future phases may allow
    multiple overlapping sessions (e.g. background buffer + hotkey).
    """

    id: int | None  # None until persisted
    started_at: datetime
    ended_at: datetime | None = None
    capture_mode: str = "hotkey"


@dataclass(frozen=True, slots=True, kw_only=True)
class Step:
    """An individual captured step."""

    id: int | None  # None until persisted
    session_id: int
    sequence: int
    captured_at: datetime
    kind: StepKind
    title: str = ""
    body_markdown: str = ""
    screenshot_path: str | None = None  # relative to case root
    """Path relative to the case directory, e.g. ``screenshots/2026….png``."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """Aggregate: metadata + the root path on disk where its files live.

    The repository layer returns these. Steps and sessions are loaded lazily
    through the repository, not eagerly attached.
    """

    info: CaseInfo
    root: Path

    @property
    def screenshots_dir(self) -> Path:
        return self.root / "screenshots"

    @property
    def db_path(self) -> Path:
        return self.root / "case.db"

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def internal_dir(self) -> Path:
        return self.root / ".inscription"


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseManifest:
    """Lightweight summary persisted alongside ``case.db`` as JSON.

    Lets the case list populate without opening every database.
    """

    case_number: str
    title: str
    examiner: str
    created_at: datetime
    updated_at: datetime
    step_count: int
    schema_version: int = SCHEMA_VERSION
    # Additional free-form tags for future filtering
    tags: list[str] = field(default_factory=list)
