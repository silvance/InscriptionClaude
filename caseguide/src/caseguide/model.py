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

SUGGESTIONS_SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(UTC)


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

    ``id`` is stable across regenerations; that's the hook completion
    tracking will use down the line. ``category`` is free-form and
    drives grouping in the panel ("acquisition", "verification",
    "analysis", "reporting", ...). ``depends_on`` is a list of other
    suggestion ids that must be acted on first; the panel can grey
    those out until their prerequisites are done.
    """

    id: str
    action: str
    category: str = ""
    priority: str = PRIORITY_RECOMMENDED
    expected_result: str = ""
    rationale: str = ""
    references: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class SuggestionsDocument:
    """The whole on-disk payload for ``.caseguide/suggestions.json``."""

    schema_version: int = SUGGESTIONS_SCHEMA_VERSION
    generated_at: datetime
    scope_summary: str = ""
    playbooks: list[str] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    caseguide_version: str = ""
