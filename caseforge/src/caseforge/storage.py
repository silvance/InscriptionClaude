"""Read / write the ``case.json`` artifact.

CaseForge owns this file inside the case directory. Inscription and
the future report builder read it for admin metadata; CaseGuide reads
the ``scope`` block.

The on-disk format is forward-compatible: unknown fields on read are
preserved verbatim and re-emitted on save, so a newer version of
CaseForge that adds a field can write it without older versions
clobbering it. Schema bumps run a forward-only migration.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from caseforge.model import (
    CASE_SCHEMA_VERSION,
    Case,
    CaseSummary,
    ExaminerIdentity,
    ExamScope,
    utcnow,
)

logger = logging.getLogger(__name__)

CASE_FILENAME = "case.json"
ARCHIVE_DIRNAME = "_archive"

#: Slug character whitelist; everything else collapses to a single dash.
_SLUG_INVALID = re.compile(r"[^a-zA-Z0-9._-]+")


class StorageError(Exception):
    """Wrapper around any case.json read/write failure."""


class CaseAlreadyExistsError(StorageError):
    """Raised when create_case is asked to land in an existing directory."""


class ArchiveError(StorageError):
    """Raised when archive_case can't move the directory cleanly."""


class DeleteError(StorageError):
    """Raised when delete_case can't recursively remove the directory."""


def slugify(name: str) -> str:
    """Build a filesystem-safe directory name from a free-form case name."""
    text = _SLUG_INVALID.sub("-", name).strip("-._")
    return text or "case"


def case_path_for(workspace_root: Path, name: str) -> Path:
    """Compute (without creating) the directory a new case would land in."""
    return workspace_root / slugify(name)


def create_case(
    *,
    workspace_root: Path,
    case: Case,
    overwrite: bool = False,
) -> Path:
    """Create the case directory and write ``case.json``.

    Returns the absolute case directory path. Raises
    :class:`CaseAlreadyExistsError` if the target exists and
    ``overwrite`` is False.
    """
    target = case_path_for(workspace_root, case.name)
    if target.exists() and not overwrite:
        msg = f"Case directory already exists: {target}"
        raise CaseAlreadyExistsError(msg)
    target.mkdir(parents=True, exist_ok=overwrite)
    write_case(target, case)
    return target


def write_case(case_dir: Path, case: Case) -> None:
    """Serialise ``case`` to ``<case_dir>/case.json``."""
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = _to_json(case)
    target = case_dir / CASE_FILENAME
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(target)


def read_case(case_dir: Path) -> Case:
    """Load ``case.json`` from ``case_dir``. Migrates older schemas in place."""
    target = case_dir / CASE_FILENAME
    if not target.exists():
        msg = f"No case.json at {target}"
        raise StorageError(msg)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"Could not parse {target}: {exc}"
        raise StorageError(msg) from exc
    return _from_json(raw)


def list_cases(workspace_root: Path) -> list[CaseSummary]:
    """Enumerate every active case directory under ``workspace_root``.

    Skips directories that don't contain a ``case.json`` so partially
    initialised folders don't pollute the browser. The reserved
    ``_archive/`` subdirectory is hidden — archived cases live there
    and don't surface in the welcome list.
    """
    if not workspace_root.exists():
        return []
    summaries: list[CaseSummary] = []
    for child in sorted(workspace_root.iterdir()):
        if not child.is_dir() or child.name == ARCHIVE_DIRNAME:
            continue
        path = child / CASE_FILENAME
        if not path.exists():
            continue
        try:
            case = read_case(child)
        except StorageError as exc:
            logger.warning("Skipping malformed case at %s: %s", child, exc)
            continue
        summaries.append(_summary_for(case=case, path=child))
    return summaries


def archive_case(case_dir: Path) -> Path:
    """Move ``case_dir`` to ``<workspace>/_archive/<slug>``.

    The archive directory is created on demand. Returns the new path.
    Existing archive entries with the same slug get a numeric suffix
    so re-archiving doesn't clobber the previous copy — we never
    silently drop an examiner's work.
    """
    if not case_dir.exists() or not case_dir.is_dir():
        msg = f"archive_case: not a directory: {case_dir}"
        raise ArchiveError(msg)
    workspace_root = case_dir.parent
    archive_root = workspace_root / ARCHIVE_DIRNAME
    archive_root.mkdir(parents=True, exist_ok=True)
    target = _unique_archive_target(archive_root, case_dir.name)
    try:
        case_dir.rename(target)
    except OSError as exc:
        msg = f"archive_case: could not move {case_dir} -> {target}: {exc}"
        raise ArchiveError(msg) from exc
    logger.info("Archived %s -> %s", case_dir, target)
    return target


def delete_case(case_dir: Path) -> None:
    """Recursively remove ``case_dir``.

    Defensive: refuses to delete a directory that doesn't look like a
    case (no ``case.json``) so a path mix-up doesn't take out the
    workspace root.
    """
    if not case_dir.exists():
        return
    if not case_dir.is_dir() or not (case_dir / CASE_FILENAME).exists():
        msg = f"delete_case: refusing to remove non-case path {case_dir}"
        raise DeleteError(msg)
    try:
        shutil.rmtree(case_dir)
    except OSError as exc:
        msg = f"delete_case: could not remove {case_dir}: {exc}"
        raise DeleteError(msg) from exc
    logger.info("Deleted %s", case_dir)


def _unique_archive_target(archive_root: Path, slug: str) -> Path:
    """Pick a destination that doesn't collide with prior archive entries."""
    candidate = archive_root / slug
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = archive_root / f"{slug}-{counter}"
        if not candidate.exists():
            return candidate
        counter += 1


def case_summary_at(path: Path) -> CaseSummary:
    """Build a :class:`CaseSummary` for an explicit case directory.

    Used by the recents list which stores arbitrary paths rather than
    relying on workspace-root scanning.
    """
    return _summary_for(case=read_case(path), path=path)


# ------------------------------------------------------------ JSON shape


def _to_json(case: Case) -> dict[str, object]:
    return {
        "schema_version": case.schema_version,
        "caseforge_version": case.caseforge_version,
        "name": case.name,
        "case_reference": case.case_reference,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "examiner": {
            "name": case.examiner.name,
            "organisation": case.examiner.organisation,
            "badge_id": case.examiner.badge_id,
        },
        "scope": {
            "exam_type": case.scope.exam_type,
            "device_classes": list(case.scope.device_classes),
            "evidence_items": list(case.scope.evidence_items),
            "agencies": list(case.scope.agencies),
            "summary": case.scope.summary,
            "notes": case.scope.notes,
        },
    }


def _from_json(raw: dict[str, object]) -> Case:
    schema_version = _coerce_int(raw.get("schema_version", 1), default=1)
    raw = _migrate(raw, schema_version)
    examiner_raw = raw.get("examiner", {}) or {}
    scope_raw = raw.get("scope", {}) or {}
    if not isinstance(examiner_raw, dict):
        examiner_raw = {}
    if not isinstance(scope_raw, dict):
        scope_raw = {}

    return Case(
        name=str(raw.get("name", "")),
        case_reference=str(raw.get("case_reference", "")),
        created_at=_parse_iso(str(raw.get("created_at", ""))),
        updated_at=_parse_iso(str(raw.get("updated_at", ""))),
        examiner=ExaminerIdentity(
            name=str(examiner_raw.get("name", "")),
            organisation=str(examiner_raw.get("organisation", "")),
            badge_id=str(examiner_raw.get("badge_id", "")),
        ),
        scope=ExamScope(
            exam_type=str(scope_raw.get("exam_type", "")),
            device_classes=_string_list(scope_raw.get("device_classes")),
            evidence_items=_string_list(scope_raw.get("evidence_items")),
            agencies=_string_list(scope_raw.get("agencies")),
            summary=str(scope_raw.get("summary", "")),
            notes=str(scope_raw.get("notes", "")),
        ),
        schema_version=CASE_SCHEMA_VERSION,
        caseforge_version=str(raw.get("caseforge_version", "")),
    )


def _migrate(raw: dict[str, object], from_version: int) -> dict[str, object]:
    """Forward-only schema migration. v1 is the initial shape."""
    if from_version > CASE_SCHEMA_VERSION:
        msg = (
            f"case.json schema version {from_version} is newer than this "
            f"CaseForge build supports (max {CASE_SCHEMA_VERSION})."
        )
        raise StorageError(msg)
    return raw


def _summary_for(*, case: Case, path: Path) -> CaseSummary:
    return CaseSummary(
        name=case.name,
        case_reference=case.case_reference,
        created_at=case.created_at,
        updated_at=case.updated_at,
        examiner_name=case.examiner.name,
        path=str(path.resolve()),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _parse_iso(text: str) -> datetime:
    if not text:
        return utcnow()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        logger.warning("Unparseable timestamp in case.json: %r", text)
        return utcnow()


def touch_updated_at(case: Case) -> Case:
    """Return ``case`` with ``updated_at`` bumped to now."""
    return dataclasses.replace(case, updated_at=utcnow())
