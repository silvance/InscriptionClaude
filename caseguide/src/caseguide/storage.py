"""Read / write ``<case-root>/.caseguide/suggestions.json``.

CaseGuide owns this file inside the case directory. The format is the
contract documented in ``inscription/docs/integration.md``; Inscription
reads it (read-only) to surface the suggestions panel.

Atomic writes: payload goes to ``suggestions.json.tmp`` and is then
renamed over the existing file so a crash mid-write can't leave the
file truncated.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from caseguide.model import (
    PRIORITY_RECOMMENDED,
    SUGGESTIONS_SCHEMA_VERSION,
    Suggestion,
    SuggestionsDocument,
    utcnow,
)

logger = logging.getLogger(__name__)

CASEGUIDE_DIRNAME = ".caseguide"
SUGGESTIONS_FILENAME = "suggestions.json"


class StorageError(Exception):
    """Wrapper around any suggestions.json read/write failure."""


def suggestions_path(case_dir: Path) -> Path:
    return case_dir / CASEGUIDE_DIRNAME / SUGGESTIONS_FILENAME


def read_suggestions(case_dir: Path) -> SuggestionsDocument | None:
    """Load the saved suggestions document, or None if not present.

    Missing file is the normal "first time CaseGuide opens this case"
    state; callers should fall back to "generate fresh" when this
    returns None.
    """
    target = suggestions_path(case_dir)
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"Could not parse {target}: {exc}"
        raise StorageError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"{target} top-level JSON must be an object"
        raise StorageError(msg)
    return _from_json(raw)


def write_suggestions(case_dir: Path, doc: SuggestionsDocument) -> Path:
    """Atomically persist ``doc`` to the case's suggestions.json."""
    target = suggestions_path(case_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _to_json(doc)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


# ------------------------------------------------------------ JSON shape


def _to_json(doc: SuggestionsDocument) -> dict[str, object]:
    return {
        "schema_version": doc.schema_version,
        "generated_at": doc.generated_at.isoformat(),
        "scope_summary": doc.scope_summary,
        "playbooks": list(doc.playbooks),
        "suggestions": [_suggestion_to_json(s) for s in doc.suggestions],
        "caseguide_version": doc.caseguide_version,
    }


def _suggestion_to_json(s: Suggestion) -> dict[str, object]:
    return {
        "id": s.id,
        "category": s.category,
        "priority": s.priority,
        "action": s.action,
        "expected_result": s.expected_result,
        "rationale": s.rationale,
        "references": list(s.references),
        "depends_on": list(s.depends_on),
        "completed": s.completed,
        "completed_at": s.completed_at.isoformat() if s.completed_at is not None else None,
    }


def _from_json(raw: dict[str, object]) -> SuggestionsDocument:
    suggestions_raw = raw.get("suggestions", [])
    if not isinstance(suggestions_raw, list):
        suggestions_raw = []
    return SuggestionsDocument(
        schema_version=_coerce_int(
            raw.get("schema_version", 1), default=SUGGESTIONS_SCHEMA_VERSION
        ),
        generated_at=_parse_iso(raw.get("generated_at")),
        scope_summary=str(raw.get("scope_summary", "")),
        playbooks=_string_list(raw.get("playbooks")),
        suggestions=[
            _suggestion_from_json(item)
            for item in suggestions_raw
            if isinstance(item, dict)
        ],
        caseguide_version=str(raw.get("caseguide_version", "")),
    )


def _suggestion_from_json(raw: dict[str, object]) -> Suggestion:
    return Suggestion(
        id=str(raw.get("id", "")),
        action=str(raw.get("action", "")),
        category=str(raw.get("category", "")),
        priority=str(raw.get("priority", PRIORITY_RECOMMENDED)),
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


def _parse_iso(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        return utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return utcnow()


def _parse_optional_iso(value: object) -> datetime | None:
    """Like ``_parse_iso`` but returns None for missing / unparseable input.

    Used for ``completed_at`` — a missing timestamp legitimately means
    "never completed", so we must not invent ``utcnow()`` as a fallback
    the way ``generated_at`` does.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _coerce_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default
