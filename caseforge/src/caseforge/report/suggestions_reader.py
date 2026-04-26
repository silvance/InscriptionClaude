"""Tolerant reader for ``<case-root>/.caseguide/suggestions.json``.

CaseForge stays decoupled from the ``caseguide`` Python package the
same way Inscription does — we read the documented filesystem
contract instead of importing CaseGuide's source. This is a near-
verbatim copy of ``inscription.caseguide_link.reader``: missing file
returns None, malformed file logs and returns None (the panel /
report layer treats both as "no suggestions section to render").

Schema versions accepted:

- v1 — original. ``completed`` / ``completed_at`` absent; defaulted
  to ``False`` / ``None``.
- v2 — adds per-suggestion completion fields.
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

#: Same cap CaseGuide writes against — bigger than any sane case,
#: smaller than anything that would slow the renderer.
_MAX_SUGGESTIONS_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseguideSuggestion:
    """One row in the suggestions feed, as the report layer sees it."""

    id: str
    action: str
    category: str = ""
    priority: str = "recommended"
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

    The report path treats every error mode as "no suggestions
    section" — a malformed or oversized file logs at WARNING and
    returns None so the renderer just skips the suggestions block
    rather than crashing the whole report.
    """
    target = suggestions_path(case_dir)
    if not target.exists():
        return None
    raw = _load_json(target)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        logger.warning("%s top-level is not an object", target)
        return None
    return _document_from_json(raw)


def _load_json(target: Path) -> object | None:
    """Read + parse ``target``, capping size and swallowing every error.

    Returns the parsed object on success, ``None`` on any failure
    (oversize, unreadable, malformed JSON). Each branch logs at
    WARNING so the operator can investigate without the report
    render itself dying.
    """
    try:
        size = target.stat().st_size
    except OSError as exc:
        logger.warning("Could not stat %s: %s", target, exc)
        return None
    if size > _MAX_SUGGESTIONS_BYTES:
        logger.warning(
            "%s is %d bytes (cap %d); skipping suggestions block in report.",
            target,
            size,
            _MAX_SUGGESTIONS_BYTES,
        )
        return None
    try:
        parsed: object = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.warning("Could not read %s: %s", target, exc)
        return None
    except ValueError as exc:
        logger.warning("Could not parse %s: %s", target, exc)
        return None
    return parsed


# ------------------------------------------------------------ parsers


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
        priority=str(raw.get("priority", "recommended")),
        expected_result=str(raw.get("expected_result", "")),
        rationale=str(raw.get("rationale", "")),
        references=_string_list(raw.get("references")),
        depends_on=_string_list(raw.get("depends_on")),
        completed=_coerce_bool(raw.get("completed"), default=False),
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


def _coerce_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _parse_optional_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
