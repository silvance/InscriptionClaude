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

CASE_SCHEMA_VERSION = 3

#: Stable identifiers for the primary forensic tool an examiner uses on a
#: case. Stored in ``ExamScope.primary_tool`` and consumed by CaseGuide
#: (which renders tool-specific playbook variants) and Inscription (which
#: feeds it to the AI-rewrite system prompt so step text comes back in
#: the right tool's vocabulary). Free-form on the way out — the schema
#: doesn't enforce one of these values, so adding a tool later is just a
#: new entry in the picker.
PRIMARY_TOOL_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "(none / unspecified)"),
    ("axiom", "Magnet AXIOM"),
    ("xways", "X-Ways Forensics"),
    ("ftk", "AccessData FTK"),
    ("autopsy", "Autopsy"),
    ("cellebrite", "Cellebrite UFED"),
    ("other", "Other (specify in notes)"),
)


def utcnow() -> datetime:
    return datetime.now(UTC)


# JSON-tolerant coercion helpers shared by storage.py, inscription_sessions.py,
# and report/. Each returns a sensible default when the input is missing,
# wrong type, or unparseable — case files we read may have been written by
# an older or partially-corrupted CaseForge install.

def coerce_int(value: object, *, default: int) -> int:
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


def parse_iso(value: object) -> datetime:
    """Return ``value`` as a datetime; fall back to utcnow on bad input."""
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return utcnow()


def parse_optional_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


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
class CustodyRecord:
    """Chain-of-custody fields captured at intake.

    The block is intentionally light — full custody logs that span
    transfers between examiners belong in a dedicated audit log
    (Tool 3's territory). What we capture here is the minimum the
    examiner fills in once when the evidence arrives.
    """

    received_at: datetime | None = None
    received_from: str = ""  # who delivered the evidence
    delivery_method: str = ""  # "in person", "carrier", "secure email", etc.
    evidence_bag_ids: list[str] = field(default_factory=list)
    seal_intact: bool | None = None  # tri-state: None = "not recorded"
    notes: str = ""


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
    primary_tool: str = ""  # one of PRIMARY_TOOL_CHOICES ids; "" = unspecified
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
    custody: CustodyRecord = field(default_factory=CustodyRecord)
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
