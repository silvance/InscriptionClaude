"""case.json reader: tolerant projection of CaseForge's contract."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from caseguide.case_reader import CASE_FILENAME, CaseReadError, read_case

if TYPE_CHECKING:
    from pathlib import Path


def _write(case_dir: Path, payload: dict[str, object]) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / CASE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")


def test_reads_v3_case_with_primary_tool(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _write(
        case_dir,
        {
            "schema_version": 3,
            "name": "Demo",
            "case_reference": "DM-1",
            "examiner": {"name": "Alex"},
            "scope": {
                "exam_type": "CSAM",
                "primary_tool": "axiom",
                "device_classes": ["windows-laptop"],
                "evidence_items": ["E01 image"],
                "agencies": ["FBI"],
                "summary": "summary",
                "notes": "notes",
            },
        },
    )
    handle = read_case(case_dir)
    assert handle.name == "Demo"
    assert handle.case_reference == "DM-1"
    assert handle.examiner_name == "Alex"
    assert handle.scope.primary_tool == "axiom"
    assert handle.scope.device_classes == ["windows-laptop"]


def test_v2_case_without_primary_tool_loads_with_default(tmp_path: Path) -> None:
    case_dir = tmp_path / "v2"
    _write(
        case_dir,
        {
            "schema_version": 2,
            "name": "Old",
            "examiner": {},
            "scope": {"exam_type": "fraud"},
        },
    )
    handle = read_case(case_dir)
    assert handle.scope.primary_tool == ""
    assert handle.scope.exam_type == "fraud"


def test_missing_case_json_raises(tmp_path: Path) -> None:
    with pytest.raises(CaseReadError):
        read_case(tmp_path)


def test_malformed_json_raises(tmp_path: Path) -> None:
    case_dir = tmp_path / "broken"
    case_dir.mkdir()
    (case_dir / CASE_FILENAME).write_text("{not valid", encoding="utf-8")
    with pytest.raises(CaseReadError):
        read_case(case_dir)


def test_unknown_extra_fields_dont_break_reader(tmp_path: Path) -> None:
    """A future schema bump that adds keys must not break CaseGuide."""
    case_dir = tmp_path / "future"
    _write(
        case_dir,
        {
            "schema_version": 99,
            "name": "Future",
            "examiner": {"name": "Alex", "tomorrow_field": "x"},
            "scope": {"exam_type": "CSAM", "tomorrow_extra": [1, 2, 3]},
            "tomorrow_block": {"nested": True},
        },
    )
    handle = read_case(case_dir)
    assert handle.name == "Future"
    assert handle.scope.exam_type == "CSAM"
