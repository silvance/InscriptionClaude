"""Domain model for CaseGuide.

A *suggestion* is one entry in the action checklist CaseGuide produces
for a given case. The on-disk shape lives at
``<case-root>/.caseguide/suggestions.json`` and matches the contract
documented in ``inscription/docs/integration.md`` so Inscription's
suggestions panel can read it without coupling.

Generation pipeline:

    case.json scope ──► PlaybookMatcher (in playbooks.py)
                          │
                          ▼
                  matching playbooks
                          │
                          ▼
                  LLM augmentation pass
                          │
                          ▼
                  list[Suggestion] ──► suggestions.json
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

SUGGESTIONS_SCHEMA_VERSION = 2


def utcnow() -> datetime:
    return datetime.now(UTC)


# JSON-tolerant coercion helpers shared across storage.py, case_reader.py,
# playbooks.py, and llm/prompt.py. Each returns a sensible default when the
# input is missing, wrong type, or unparseable.

def coerce_int(value: object, *, default: int) -> int:
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


def coerce_bool(value: object, *, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def parse_iso(value: object, *, default: datetime | None) -> datetime | None:
    """Parse an ISO 8601 timestamp; return ``default`` if absent or invalid.

    Callers pick the fallback explicitly: ``default=utcnow()`` for fields
    that need *some* timestamp; ``default=None`` for optional fields.
    """
    if not isinstance(value, str) or not value:
        return default
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return default


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


#: Stable priority labels. The picker uses these verbatim; downstream
#: tools can sort / filter on the exact string.
PRIORITY_REQUIRED = "required"
PRIORITY_RECOMMENDED = "recommended"
PRIORITY_OPTIONAL = "optional"
PRIORITY_CHOICES: tuple[str, ...] = (
    PRIORITY_REQUIRED,
    PRIORITY_RECOMMENDED,
    PRIORITY_OPTIONAL,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Suggestion:
    """One entry in the suggestions feed.

    ``id`` is stable across regenerations; the completion tracker
    keys on it so the LLM Refine pass doesn't undo "verified" steps.
    ``category`` is free-form and drives grouping in the panel
    ("acquisition", "verification", "analysis", "reporting", ...).
    ``depends_on`` is a list of other suggestion ids that must be
    acted on first; the panel can grey those out until their
    prerequisites are done.

    ``completed`` plus ``completed_at`` are the per-entry tracker
    state. Once marked complete, the row dims and the LLM Refine
    pass leaves it untouched.
    """

    id: str
    action: str
    category: str = ""
    priority: str = PRIORITY_RECOMMENDED
    expected_result: str = ""
    rationale: str = ""
    references: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    completed: bool = False
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SuggestionsDocument:
    """The whole on-disk payload for ``.caseguide/suggestions.json``."""

    schema_version: int = SUGGESTIONS_SCHEMA_VERSION
    generated_at: datetime
    scope_summary: str = ""
    playbooks: list[str] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    caseguide_version: str = ""
