"""Marker file for "this session has been submitted as evidence".

A submitted session is read-only: the workspace shows a banner,
edit operations are gated behind an explicit "Reopen for editing"
prompt, and the operator has a clear visual signal that this case
has already been handed over (and any further edits will diverge
from what's in the discovery package).

Stored as a JSON file at ``<session>/.inscription/submitted.json``
rather than a column on ``session_info`` so we don't need a schema
migration just to track an in-app workflow flag, and so the marker
travels with the session directory if it's moved between machines.

The marker is intentionally narrow: just *when* it was submitted
and (optionally) which export format / examiner produced the
submission. Cases where a session needs to be reopened still wipe
this marker entirely; the audit story for "this was unlocked at
HH:MM:SS by Alex Smith" lives in the operator's external case
log, not this file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from inscription.model import utcnow

if TYPE_CHECKING:
    from inscription.model import Session

logger = logging.getLogger(__name__)

#: Filename inside the session's ``.inscription/`` directory.
_FILENAME = "submitted.json"


@dataclass(frozen=True, slots=True, kw_only=True)
class SubmittedMarker:
    """Snapshot of when a session was marked submitted, and by whom."""

    submitted_at: datetime
    examiner: str | None = None
    export_format: str | None = None


def marker_path(session: Session) -> object:
    """Return the marker file's path on disk.

    Exposed as a free function so tests / external tools can poke at
    the file without instantiating a Session-managing harness. Returns
    a ``Path`` but typed as ``object`` here to keep the public type
    surface tight when callers don't need it.
    """
    return session.internal_dir / _FILENAME


def read(session: Session) -> SubmittedMarker | None:
    """Return the marker for ``session``, or ``None`` when not submitted.

    Defensive against the file being absent (the common case for an
    in-progress session) and against a corrupt / partial JSON write
    from a crash mid-mark (treat as "not submitted" so the operator
    isn't blocked by a stale marker).
    """
    path = session.internal_dir / _FILENAME
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        logger.warning("Unreadable submitted marker at %s; treating as not submitted", path)
        return None
    submitted_at_raw = data.get("submitted_at")
    if not isinstance(submitted_at_raw, str):
        return None
    try:
        submitted_at = datetime.fromisoformat(submitted_at_raw)
    except ValueError:
        return None
    examiner = data.get("examiner")
    fmt = data.get("export_format")
    return SubmittedMarker(
        submitted_at=submitted_at,
        examiner=examiner if isinstance(examiner, str) else None,
        export_format=fmt if isinstance(fmt, str) else None,
    )


def mark(
    session: Session,
    *,
    examiner: str | None = None,
    export_format: str | None = None,
) -> SubmittedMarker:
    """Mark ``session`` as submitted, returning the resulting marker.

    Overwrites any prior marker (re-submitting after an unlock-and-
    re-edit produces a fresh ``submitted_at``). The .inscription/
    directory is created if missing -- it always should exist for an
    open session, but be defensive in case a caller writes the
    marker before opening the session.
    """
    marker = SubmittedMarker(
        submitted_at=utcnow(),
        examiner=examiner,
        export_format=export_format,
    )
    payload = {"submitted_at": marker.submitted_at.isoformat()}
    if marker.examiner is not None:
        payload["examiner"] = marker.examiner
    if marker.export_format is not None:
        payload["export_format"] = marker.export_format

    session.internal_dir.mkdir(parents=True, exist_ok=True)
    path = session.internal_dir / _FILENAME
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "Marked session %r as submitted at %s",
        session.info.name,
        marker.submitted_at.isoformat(),
    )
    return marker


def clear(session: Session) -> None:
    """Remove the submitted marker, returning the session to editable.

    No-op if no marker exists. Logged so the operator's debug log
    captures the reopen event even though this isn't a full audit
    trail.
    """
    path = session.internal_dir / _FILENAME
    if not path.exists():
        return
    path.unlink()
    logger.info("Cleared submitted marker for session %r", session.info.name)
