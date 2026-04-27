"""Tolerant JSON reader for ``<case-root>/.caseguide/suggestions.json``.

Inscription deliberately does not import from the ``caseguide`` package —
they're sibling apps that communicate through the on-disk contract
documented in :file:`inscription/docs/integration.md`. This module
parses that file into local dataclasses so a missing or stale CaseGuide
install never breaks Inscription.

Schema versions accepted:

- v1 — original. ``completed`` / ``completed_at`` absent; we default
  them to ``False`` / ``None`` so a v1 file renders as "all open".
- v2 — adds per-suggestion completion fields.

Forensic workstations may have an older or partially-written
suggestions.json; the panel hides itself when this module returns
``None``, so the user just sees the regular Inscription experience
instead of an error.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

CASEGUIDE_DIRNAME = ".caseguide"
SUGGESTIONS_FILENAME = "suggestions.json"

PRIORITY_REQUIRED = "required"
PRIORITY_RECOMMENDED = "recommended"
PRIORITY_OPTIONAL = "optional"


class SuggestionsReadError(Exception):
    """Raised when the file is present but unparseable.

    Callers treat this the same as "no file" for UI purposes — surfaced
    to logs so the underlying problem isn't silent, but the panel still
    degrades to hidden rather than crashing.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseguideSuggestion:
    """One row in the suggestions feed, as Inscription sees it."""

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
class CaseguideDocument:
    """Top-level shape of suggestions.json."""

    schema_version: int
    generated_at: datetime | None
    scope_summary: str
    playbooks: list[str]
    suggestions: list[CaseguideSuggestion]
    caseguide_version: str = ""


def suggestions_path(case_dir: Path) -> Path:
    return case_dir / CASEGUIDE_DIRNAME / SUGGESTIONS_FILENAME


def read_suggestions(case_dir: Path) -> CaseguideDocument | None:
    """Load CaseGuide's suggestions for ``case_dir``, or ``None``.

    Returns ``None`` when the file isn't present (the dominant path —
    most cases run without CaseGuide). Raises :class:`SuggestionsReadError`
    when the file exists but can't be parsed; the caller logs and
    treats it as "no panel".
    """
    target = suggestions_path(case_dir)
    if not target.exists():
        return None
    try:
        raw_text = target.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"Could not read {target}: {exc}"
        raise SuggestionsReadError(msg) from exc
    try:
        raw = json.loads(raw_text)
    except ValueError as exc:
        msg = f"{target} contains invalid JSON: {exc}"
        raise SuggestionsReadError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"{target} top-level JSON must be an object"
        raise SuggestionsReadError(msg)
    return _document_from_json(raw)


def _document_from_json(raw: dict[str, object]) -> CaseguideDocument:
    suggestions_raw = raw.get("suggestions", [])
    suggestions_list = suggestions_raw if isinstance(suggestions_raw, list) else []
    return CaseguideDocument(
        schema_version=_coerce_int(raw.get("schema_version"), default=1),
        generated_at=_parse_optional_iso(raw.get("generated_at")),
        scope_summary=str(raw.get("scope_summary", "")),
        playbooks=_string_list(raw.get("playbooks")),
        suggestions=[
            _suggestion_from_json(item)
            for item in suggestions_list
            if isinstance(item, dict)
        ],
        caseguide_version=str(raw.get("caseguide_version", "")),
    )


def _suggestion_from_json(raw: dict[str, object]) -> CaseguideSuggestion:
    return CaseguideSuggestion(
        id=str(raw.get("id", "")),
        action=str(raw.get("action", "")),
        category=str(raw.get("category", "")),
        priority=str(raw.get("priority", PRIORITY_RECOMMENDED)),
        expected_result=str(raw.get("expected_result", "")),
        rationale=str(raw.get("rationale", "")),
        references=_string_list(raw.get("references")),
        depends_on=_string_list(raw.get("depends_on")),
        completed=isinstance(raw.get("completed"), bool) and bool(raw.get("completed")),
        completed_at=_parse_optional_iso(raw.get("completed_at")),
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


def _parse_optional_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
