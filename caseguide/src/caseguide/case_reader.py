"""Read ``case.json`` written by CaseForge.

CaseGuide stays decoupled from the CaseForge Python package — both
tools talk through the filesystem contract documented in
``inscription/docs/integration.md``. This module is the minimal
projection of that contract: just the fields CaseGuide actually
consumes (scope + display info), tolerated against schema bumps in
the same way Inscription handles missing manifest fields.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CASE_FILENAME = "case.json"

# Hard cap on the case.json size we'll load. CaseForge writes files in
# the low-tens-of-KB range; refuse to ingest anything wildly larger to
# bound our memory exposure to corrupt or stale files.
_MAX_CASE_BYTES = 5 * 1024 * 1024


class CaseReadError(Exception):
    """Raised when case.json is missing or malformed."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseScope:
    """The :class:`caseforge.model.ExamScope` projection CaseGuide uses."""

    exam_type: str = ""
    primary_tool: str = ""
    device_classes: list[str] = field(default_factory=list)
    evidence_items: list[str] = field(default_factory=list)
    agencies: list[str] = field(default_factory=list)
    summary: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseHandle:
    """Just enough of ``case.json`` for CaseGuide to render and reason about."""

    name: str
    case_reference: str
    examiner_name: str
    scope: CaseScope
    schema_version: int = 1


def read_case(case_dir: Path) -> CaseHandle:
    """Load the case.json for ``case_dir`` into a :class:`CaseHandle`."""
    target = case_dir / CASE_FILENAME
    if not target.exists():
        msg = f"No case.json at {target}"
        raise CaseReadError(msg)
    try:
        size = target.stat().st_size
    except OSError as exc:
        msg = f"Could not stat {target}: {exc}"
        raise CaseReadError(msg) from exc
    if size > _MAX_CASE_BYTES:
        msg = f"{target} is {size} bytes; refusing to load (cap is {_MAX_CASE_BYTES})."
        raise CaseReadError(msg)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"Could not parse {target}: {exc}"
        raise CaseReadError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"{target}: top-level JSON must be an object"
        raise CaseReadError(msg)

    examiner_raw = raw.get("examiner", {}) or {}
    if not isinstance(examiner_raw, dict):
        examiner_raw = {}
    scope_raw = raw.get("scope", {}) or {}
    if not isinstance(scope_raw, dict):
        scope_raw = {}

    return CaseHandle(
        name=str(raw.get("name", "")),
        case_reference=str(raw.get("case_reference", "")),
        examiner_name=str(examiner_raw.get("name", "")),
        scope=CaseScope(
            exam_type=str(scope_raw.get("exam_type", "")),
            primary_tool=str(scope_raw.get("primary_tool", "")),
            device_classes=_string_list(scope_raw.get("device_classes")),
            evidence_items=_string_list(scope_raw.get("evidence_items")),
            agencies=_string_list(scope_raw.get("agencies")),
            summary=str(scope_raw.get("summary", "")),
            notes=str(scope_raw.get("notes", "")),
        ),
        schema_version=_coerce_int(raw.get("schema_version", 1), default=1),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


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
