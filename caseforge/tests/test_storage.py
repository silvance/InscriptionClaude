"""case.json round-trip + listing."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from caseforge.model import Case, ExaminerIdentity, ExamScope, utcnow
from caseforge.storage import (
    CASE_FILENAME,
    CaseAlreadyExistsError,
    StorageError,
    case_path_for,
    create_case,
    list_cases,
    read_case,
    slugify,
    touch_updated_at,
    write_case,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_case(name: str = "Operation Stardust") -> Case:
    now = utcnow()
    return Case(
        name=name,
        case_reference="HSV-2026-0317",
        created_at=now,
        updated_at=now,
        examiner=ExaminerIdentity(name="Alex Smith", organisation="CCU", badge_id="CCU-0421"),
        scope=ExamScope(
            exam_type="CSAM possession",
            device_classes=["windows-laptop"],
            evidence_items=["E01 image"],
            agencies=["FBI"],
            summary="Image acquired off subject laptop.",
            notes="Custody form on file.",
        ),
    )


def test_slugify_handles_messy_input() -> None:
    assert slugify("Operation Stardust") == "Operation-Stardust"
    assert slugify("HSV/2026:0317") == "HSV-2026-0317"
    assert slugify("...weird...") == "weird"
    assert slugify("") == "case"


def test_create_case_writes_case_json(tmp_path: Path) -> None:
    case = _make_case()
    target = create_case(workspace_root=tmp_path, case=case)
    assert target == case_path_for(tmp_path, case.name)
    assert (target / CASE_FILENAME).exists()


def test_create_case_refuses_duplicate(tmp_path: Path) -> None:
    case = _make_case()
    create_case(workspace_root=tmp_path, case=case)
    with pytest.raises(CaseAlreadyExistsError):
        create_case(workspace_root=tmp_path, case=case)


def test_create_case_overwrite_replaces_existing(tmp_path: Path) -> None:
    case = _make_case()
    create_case(workspace_root=tmp_path, case=case)
    create_case(workspace_root=tmp_path, case=case, overwrite=True)


def test_round_trip_preserves_every_field(tmp_path: Path) -> None:
    case = _make_case()
    target = create_case(workspace_root=tmp_path, case=case)
    loaded = read_case(target)
    assert loaded.name == case.name
    assert loaded.case_reference == case.case_reference
    assert loaded.examiner == case.examiner
    assert loaded.scope == case.scope


def test_read_case_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        read_case(tmp_path / "nope")


def test_list_cases_skips_directories_without_case_json(tmp_path: Path) -> None:
    case = _make_case()
    create_case(workspace_root=tmp_path, case=case)
    (tmp_path / "stray-folder").mkdir()
    summaries = list_cases(tmp_path)
    assert len(summaries) == 1
    assert summaries[0].name == case.name
    assert summaries[0].case_reference == case.case_reference


def test_write_case_is_atomic_and_updates_timestamp(tmp_path: Path) -> None:
    case = _make_case()
    target = create_case(workspace_root=tmp_path, case=case)
    bumped = touch_updated_at(case)
    write_case(target, bumped)
    loaded = read_case(target)
    assert loaded.updated_at >= case.updated_at


def test_unknown_future_schema_version_raises(tmp_path: Path) -> None:
    case = _make_case()
    target = create_case(workspace_root=tmp_path, case=case)
    payload = json.loads((target / CASE_FILENAME).read_text(encoding="utf-8"))
    payload["schema_version"] = 99
    (target / CASE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StorageError, match="newer"):
        read_case(target)
