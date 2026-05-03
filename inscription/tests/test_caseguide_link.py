"""Tolerant reader for CaseGuide's suggestions.json (Inscription side)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from inscription.caseguide_link import (
    CaseguideDocument,
    SuggestionsReadError,
    read_suggestions,
    suggestions_path,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_suggestions(case_dir: Path, payload: dict[str, object]) -> None:
    target = suggestions_path(case_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def test_returns_none_when_file_missing(tmp_path: Path) -> None:
    case_dir = tmp_path / "fresh"
    case_dir.mkdir()
    assert read_suggestions(case_dir) is None


def test_round_trips_v2_payload(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _write_suggestions(
        case_dir,
        {
            "schema_version": 2,
            "generated_at": "2026-04-25T14:30:00+00:00",
            "scope_summary": "CSAM possession; Win11.",
            "playbooks": ["NIST SP 800-86"],
            "suggestions": [
                {
                    "id": "verify-image-hash",
                    "category": "verification",
                    "priority": "required",
                    "action": "Verify the SHA-256.",
                    "expected_result": "Hash matches log.",
                    "rationale": "Establishes integrity.",
                    "references": ["NIST SP 800-86 §5.2.2"],
                    "depends_on": [],
                    "completed": True,
                    "completed_at": "2026-04-25T15:02:11+00:00",
                },
                {
                    "id": "open-step",
                    "action": "Pending step.",
                    "priority": "recommended",
                    "depends_on": ["verify-image-hash"],
                    "completed": False,
                    "completed_at": None,
                },
            ],
            "caseguide_version": "0.1.0a0",
        },
    )

    doc = read_suggestions(case_dir)
    assert isinstance(doc, CaseguideDocument)
    assert doc.schema_version == 2
    assert doc.scope_summary == "CSAM possession; Win11."
    assert [s.id for s in doc.suggestions] == ["verify-image-hash", "open-step"]
    done, pending = doc.suggestions
    assert done.completed is True
    assert done.completed_at == datetime(2026, 4, 25, 15, 2, 11, tzinfo=UTC)
    assert done.references == ["NIST SP 800-86 §5.2.2"]
    assert pending.completed is False
    assert pending.completed_at is None
    assert pending.depends_on == ["verify-image-hash"]


def test_v1_payload_loads_with_default_completion(tmp_path: Path) -> None:
    """A v1 file (no completion fields) should still parse cleanly."""
    case_dir = tmp_path / "legacy"
    _write_suggestions(
        case_dir,
        {
            "schema_version": 1,
            "generated_at": "2026-04-01T12:00:00+00:00",
            "scope_summary": "Old case.",
            "playbooks": [],
            "suggestions": [
                {
                    "id": "verify-image-hash",
                    "action": "Verify hash.",
                    "priority": "required",
                },
            ],
            "caseguide_version": "0.1.0a0",
        },
    )
    doc = read_suggestions(case_dir)
    assert doc is not None
    assert doc.suggestions[0].completed is False
    assert doc.suggestions[0].completed_at is None


def test_unknown_fields_are_ignored(tmp_path: Path) -> None:
    """Forward compatibility: an extra v3-only field must not raise."""
    case_dir = tmp_path / "future"
    _write_suggestions(
        case_dir,
        {
            "schema_version": 3,
            "scope_summary": "Future case.",
            "suggestions": [
                {
                    "id": "x",
                    "action": "Hi.",
                    "priority": "required",
                    "future_only_field": {"weird": True},
                },
            ],
            "future_only_top_level": [1, 2, 3],
        },
    )
    doc = read_suggestions(case_dir)
    assert doc is not None
    assert doc.suggestions[0].action == "Hi."


def test_malformed_json_raises(tmp_path: Path) -> None:
    case_dir = tmp_path / "broken"
    target = suggestions_path(case_dir)
    target.parent.mkdir(parents=True)
    target.write_text("{this is not json", encoding="utf-8")
    with pytest.raises(SuggestionsReadError):
        read_suggestions(case_dir)


def test_top_level_array_raises(tmp_path: Path) -> None:
    case_dir = tmp_path / "array-root"
    target = suggestions_path(case_dir)
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps([{"id": "x", "action": "y"}]), encoding="utf-8")
    with pytest.raises(SuggestionsReadError):
        read_suggestions(case_dir)


def test_non_dict_suggestions_are_skipped(tmp_path: Path) -> None:
    """Stray non-object entries in the array shouldn't break the load."""
    case_dir = tmp_path / "mixed"
    _write_suggestions(
        case_dir,
        {
            "schema_version": 2,
            "scope_summary": "",
            "suggestions": [
                {"id": "good", "action": "Real one.", "priority": "required"},
                "this should be ignored",
                None,
                42,
            ],
        },
    )
    doc = read_suggestions(case_dir)
    assert doc is not None
    assert [s.id for s in doc.suggestions] == ["good"]


def test_oversized_file_refuses_to_load(tmp_path: Path) -> None:
    """Hard cap on the suggestions.json size we'll load. Mirrors the
    pattern in caseforge/storage.py and report/suggestions_reader.py
    so a corrupt or hostile file can't OOM the recorder."""
    case_dir = tmp_path / "case"
    target = suggestions_path(case_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exceed the 10 MiB cap by a hair -- enough to trip the stat check
    # but not enough to actually allocate that much in pytest.
    big = b' ' * (10 * 1024 * 1024 + 1)
    target.write_bytes(big)
    with pytest.raises(SuggestionsReadError, match="refusing to load"):
        read_suggestions(case_dir)
