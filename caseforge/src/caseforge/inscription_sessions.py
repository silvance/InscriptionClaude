"""Read Inscription session manifests from a case directory.

CaseForge is read-only on Inscription's output: it walks the case
directory, parses each ``<session-slug>/manifest.json``, and returns a
list of :class:`InscriptionSession` summaries for the case view's
"Sessions" tab. We deliberately avoid opening Inscription's
``session.db`` to keep CaseForge dependency-free of SQLite parsing —
the manifest carries everything the case home page needs.

The manifest schema lives in Inscription
(``inscription/storage/manifest.py``) and is part of the integration
contract documented in ``inscription/docs/integration.md``. CaseForge
tolerates missing or extra fields so a future Inscription bump that
adds keys doesn't break this view.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from caseforge.model import utcnow

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True, slots=True, kw_only=True)
class InscriptionSession:
    """One Inscription session's manifest summary."""

    slug: str
    name: str
    started_at: datetime
    ended_at: datetime | None
    event_count: int
    step_count: int
    path: str

    @property
    def is_in_progress(self) -> bool:
        return self.ended_at is None


def list_inscription_sessions(case_dir: Path) -> list[InscriptionSession]:
    """Return every Inscription session under ``case_dir``, newest first.

    Subdirectories without a manifest are silently skipped (a partially
    initialised or non-Inscription folder shouldn't break the case
    view). Malformed manifests are logged and skipped.
    """
    if not case_dir.exists() or not case_dir.is_dir():
        return []
    sessions: list[InscriptionSession] = []
    for child in sorted(case_dir.iterdir()):
        if not child.is_dir():
            continue
        manifest_path = child / MANIFEST_FILENAME
        if not manifest_path.exists():
            continue
        parsed = _parse_manifest(manifest_path, slug=child.name)
        if parsed is not None:
            sessions.append(parsed)
    sessions.sort(key=lambda s: s.started_at, reverse=True)
    return sessions


def _parse_manifest(path: Path, *, slug: str) -> InscriptionSession | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Skipping malformed manifest %s: %s", path, exc)
        return None
    if not isinstance(raw, dict):
        logger.warning("Manifest %s is not a JSON object", path)
        return None
    return InscriptionSession(
        slug=slug,
        name=str(raw.get("name") or slug),
        started_at=_parse_iso(raw.get("started_at")),
        ended_at=_parse_optional_iso(raw.get("ended_at")),
        event_count=_coerce_int(raw.get("event_count"), default=0),
        step_count=_coerce_int(raw.get("step_count"), default=0),
        path=str(path.parent.resolve()),
    )


def _parse_iso(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        return utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return utcnow()


def _parse_optional_iso(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default
