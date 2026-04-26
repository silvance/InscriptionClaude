"""suggestions.json round-trip + missing-file behaviour."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from caseguide.model import (
    PRIORITY_REQUIRED,
    Suggestion,
    SuggestionsDocument,
    utcnow,
)
from caseguide.storage import (
    SUGGESTIONS_FILENAME,
    StorageError,
    read_suggestions,
    suggestions_path,
    write_suggestions,
)

if TYPE_CHECKING:
    from pathlib import Path


def _doc() -> SuggestionsDocument:
    return SuggestionsDocument(
        generated_at=utcnow(),
        scope_summary="CSAM possession on a Win11 laptop.",
        playbooks=["axiom-ci-processing", "verify-image-hash"],
        suggestions=[
            Suggestion(
                id="verify-image-hash",
                action="Verify SHA-256 of the acquired image.",
                category="verification",
                priority=PRIORITY_REQUIRED,
                expected_result="Hash matches acquisition log.",
                rationale="Establishes evidence integrity before analysis.",
                references=["NIST SP 800-86 §5.2.2"],
            ),
            Suggestion(
                id="axiom-process-keywords",
                action="Run AXIOM Process keyword search with the case keyword list.",
                category="processing",
                depends_on=["verify-image-hash"],
            ),
        ],
        caseguide_version="0.1.0a0",
    )


def test_round_trip_preserves_every_field(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    target = write_suggestions(case_dir, _doc())
    assert target == suggestions_path(case_dir)
    assert target.exists()

    loaded = read_suggestions(case_dir)
    assert loaded is not None
    assert loaded.scope_summary == "CSAM possession on a Win11 laptop."
    assert [s.id for s in loaded.suggestions] == ["verify-image-hash", "axiom-process-keywords"]
    assert loaded.suggestions[0].priority == PRIORITY_REQUIRED
    assert loaded.suggestions[1].depends_on == ["verify-image-hash"]


def test_read_returns_none_when_missing(tmp_path: Path) -> None:
    case_dir = tmp_path / "fresh-case"
    case_dir.mkdir()
    assert read_suggestions(case_dir) is None


def test_read_raises_on_malformed_json(tmp_path: Path) -> None:
    case_dir = tmp_path / "broken"
    case_dir.mkdir()
    target = suggestions_path(case_dir)
    target.parent.mkdir()
    target.write_text("{not valid", encoding="utf-8")
    with pytest.raises(StorageError):
        read_suggestions(case_dir)


def test_atomic_write_does_not_leave_tmp_behind(tmp_path: Path) -> None:
    case_dir = tmp_path / "atomic"
    case_dir.mkdir()
    write_suggestions(case_dir, _doc())
    leftover = list(case_dir.glob("**/*.tmp"))
    assert leftover == []
    assert (case_dir / ".caseguide" / SUGGESTIONS_FILENAME).exists()


def test_round_trip_preserves_completion_state(tmp_path: Path) -> None:
    case_dir = tmp_path / "completed"
    case_dir.mkdir()
    completed_at = datetime(2026, 4, 25, 14, 30, tzinfo=UTC)
    doc = SuggestionsDocument(
        generated_at=utcnow(),
        suggestions=[
            Suggestion(
                id="verify-image-hash",
                action="Verify SHA-256 of acquired image.",
                priority=PRIORITY_REQUIRED,
                completed=True,
                completed_at=completed_at,
            ),
            Suggestion(id="open", action="Pending step.", priority=PRIORITY_REQUIRED),
        ],
    )
    write_suggestions(case_dir, doc)
    loaded = read_suggestions(case_dir)
    assert loaded is not None
    done, pending = loaded.suggestions
    assert done.completed is True
    assert done.completed_at == completed_at
    assert pending.completed is False
    assert pending.completed_at is None


def test_v1_file_loads_with_default_completion(tmp_path: Path) -> None:
    """A v1 suggestions.json (no completion fields) should still load."""
    case_dir = tmp_path / "legacy"
    target = suggestions_path(case_dir)
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-04-01T12:00:00+00:00",
                "scope_summary": "Old case",
                "playbooks": [],
                "suggestions": [
                    {
                        "id": "verify-image-hash",
                        "action": "Verify SHA-256.",
                        "priority": "required",
                    },
                ],
                "caseguide_version": "0.1.0a0",
            }
        ),
        encoding="utf-8",
    )
    loaded = read_suggestions(case_dir)
    assert loaded is not None
    assert loaded.suggestions[0].completed is False
    assert loaded.suggestions[0].completed_at is None
