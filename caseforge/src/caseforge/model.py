"""Domain model for CaseForge.

CaseForge owns ``case.json`` inside the case directory the suite shares
on disk. The schema below is the contract Inscription, CaseGuide, and
the report builder all read against — bumps to ``schema_version`` ship
with a forward-only migration in :mod:`caseforge.storage`.

A *case* is the top-level unit. It carries a free-form display name, an
external case reference (the agency / customer's identifier), the
examiner's identity at intake time, and a structured scope block that
CaseGuide consumes to generate a procedural checklist tailored to the
exam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

CASE_SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExaminerIdentity:
    """Who's working the case at intake. Inscription mirrors these
    fields into its forensic-notes header at export time."""

    name: str = ""
    organisation: str = ""
    badge_id: str = ""

    @property
    def is_present(self) -> bool:
        return bool(self.name.strip())


@dataclass(frozen=True, slots=True, kw_only=True)
class ExamScope:
    """Structured scope CaseGuide consumes to build its checklist.

    Free-form strings stay free-form (``summary``, ``notes``); the lists
    are vocabularies the future CaseGuide will pattern-match against
    when picking playbooks. v0.1 doesn't enforce a controlled vocabulary
    — examiners type whatever fits — but the data shape is reserved.
    """

    exam_type: str = ""  # e.g. "CSAM possession", "fraud", "IP theft"
    device_classes: list[str] = field(default_factory=list)
    evidence_items: list[str] = field(default_factory=list)
    agencies: list[str] = field(default_factory=list)
    summary: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """The full ``case.json`` payload."""

    name: str
    case_reference: str = ""
    created_at: datetime
    updated_at: datetime
    examiner: ExaminerIdentity = field(default_factory=ExaminerIdentity)
    scope: ExamScope = field(default_factory=ExamScope)
    schema_version: int = CASE_SCHEMA_VERSION
    caseforge_version: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseSummary:
    """Lightweight listing entry for the case browser.

    Built from ``case.json`` plus the directory path so the browser
    doesn't need the full case payload in memory for every row.
    """

    name: str
    case_reference: str
    created_at: datetime
    updated_at: datetime
    examiner_name: str
    path: str  # absolute directory path
