"""case.json round-trip + listing."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from caseforge.model import Case, CustodyRecord, ExaminerIdentity, ExamScope, utcnow
from caseforge.storage import (
    ARCHIVE_DIRNAME,
    CASE_FILENAME,
    ArchiveError,
    CaseAlreadyExistsError,
    DeleteError,
    StorageError,
    archive_case,
    case_path_for,
    create_case,
    delete_case,
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
            primary_tool="axiom",
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
    # Specifically: the v3 primary_tool field round-trips.
    assert loaded.scope.primary_tool == "axiom"


def test_use_caseguide_round_trips(tmp_path: Path) -> None:
    """The opt-in flag for CaseGuide-required validation persists to
    case.json so the dialog re-checks the box on next open."""
    case = _make_case()
    case = dataclasses.replace(case, scope=dataclasses.replace(case.scope, use_caseguide=True))
    target = create_case(workspace_root=tmp_path, case=case)
    loaded = read_case(target)
    assert loaded.scope.use_caseguide is True


def test_use_caseguide_defaults_false_for_legacy_cases(tmp_path: Path) -> None:
    """Older case.json files that predate the opt-in flag load with
    use_caseguide=False so existing behaviour is preserved."""
    case_dir = tmp_path / "no-flag"
    case_dir.mkdir()
    payload = {
        "schema_version": 3,
        "name": "Legacy no-flag",
        "case_reference": "LNF-1",
        "created_at": "2026-04-01T00:00:00+00:00",
        "updated_at": "2026-04-01T00:00:00+00:00",
        "examiner": {"name": "Alex", "organisation": "", "badge_id": ""},
        "scope": {
            "exam_type": "fraud",
            "primary_tool": "axiom",
            "device_classes": [],
            "evidence_items": [],
            "agencies": [],
            "summary": "",
            "notes": "",
            # Note: no use_caseguide key.
        },
        "custody": {
            "received_at": None,
            "received_from": "",
            "delivery_method": "",
            "evidence_bag_ids": [],
            "seal_intact": None,
            "notes": "",
        },
    }
    (case_dir / CASE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    loaded = read_case(case_dir)
    assert loaded.scope.use_caseguide is False


def test_v2_case_json_loads_with_default_primary_tool(tmp_path: Path) -> None:
    """A v2 case.json (no scope.primary_tool) opens with primary_tool='' and
    upgrades to v3 on next save."""
    case_dir = tmp_path / "v2-legacy"
    case_dir.mkdir()
    payload = {
        "schema_version": 2,
        "name": "Legacy v2",
        "case_reference": "LV2-1",
        "created_at": "2026-04-01T00:00:00+00:00",
        "updated_at": "2026-04-01T00:00:00+00:00",
        "examiner": {"name": "Alex", "organisation": "", "badge_id": ""},
        "scope": {
            "exam_type": "fraud",
            "device_classes": ["windows-desktop"],
            "evidence_items": ["E01 image"],
            "agencies": [],
            "summary": "",
            "notes": "",
        },
        "custody": {
            "received_at": None,
            "received_from": "",
            "delivery_method": "",
            "evidence_bag_ids": [],
            "seal_intact": None,
            "notes": "",
        },
    }
    (case_dir / CASE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    loaded = read_case(case_dir)
    assert loaded.schema_version == 3
    assert loaded.scope.primary_tool == ""
    # Other fields untouched.
    assert loaded.scope.exam_type == "fraud"
    assert loaded.scope.device_classes == ["windows-desktop"]


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


def test_archive_case_moves_directory_into_archive(tmp_path: Path) -> None:
    case = _make_case()
    target = create_case(workspace_root=tmp_path, case=case)
    moved = archive_case(target)
    assert moved.parent.name == ARCHIVE_DIRNAME
    assert moved.exists()
    assert not target.exists()
    # The browser shouldn't surface archived cases.
    assert list_cases(tmp_path) == []


def test_archive_case_disambiguates_collisions(tmp_path: Path) -> None:
    case = _make_case()
    first = create_case(workspace_root=tmp_path, case=case)
    archive_case(first)
    second = create_case(workspace_root=tmp_path, case=case)
    moved = archive_case(second)
    # The second move should land at a numbered slug to avoid clobber.
    assert moved.name == f"{first.name}-2"


def test_archive_refuses_non_directory(tmp_path: Path) -> None:
    with pytest.raises(ArchiveError):
        archive_case(tmp_path / "no-such-dir")


def test_delete_case_removes_directory_recursively(tmp_path: Path) -> None:
    case = _make_case()
    target = create_case(workspace_root=tmp_path, case=case)
    # Pretend Inscription wrote a session in there.
    (target / "session-1").mkdir()
    (target / "session-1" / "manifest.json").write_text("{}", encoding="utf-8")
    delete_case(target)
    assert not target.exists()


def test_delete_refuses_paths_that_arent_cases(tmp_path: Path) -> None:
    """Defensive: a path mix-up shouldn't blow away the workspace root."""
    not_a_case = tmp_path / "bare"
    not_a_case.mkdir()
    with pytest.raises(DeleteError):
        delete_case(not_a_case)
    assert not_a_case.exists()


def test_delete_missing_case_is_a_noop(tmp_path: Path) -> None:
    delete_case(tmp_path / "no-such-case")  # should not raise


def _make_case_with_custody() -> Case:
    now = utcnow()
    return Case(
        name="Custody Demo",
        case_reference="CD-1",
        created_at=now,
        updated_at=now,
        examiner=ExaminerIdentity(name="Alex"),
        scope=ExamScope(),
        custody=CustodyRecord(
            received_at=datetime(2026, 4, 24, 9, 30, tzinfo=UTC),
            received_from="Det. Wilkes",
            delivery_method="in person",
            evidence_bag_ids=["EB-12345", "EB-12346"],
            seal_intact=True,
            notes="Seal photographed at intake.",
        ),
    )


def test_custody_round_trips_through_case_json(tmp_path: Path) -> None:
    case = _make_case_with_custody()
    target = create_case(workspace_root=tmp_path, case=case)
    loaded = read_case(target)
    assert loaded.custody == case.custody


def test_v1_case_json_loads_with_default_custody(tmp_path: Path) -> None:
    """A case.json written before the v2 schema (no ``custody`` key) should
    open cleanly with an empty CustodyRecord and be re-saved as v2."""
    case_dir = tmp_path / "legacy"
    case_dir.mkdir()
    payload = {
        "schema_version": 1,
        "name": "Legacy",
        "case_reference": "LG-1",
        "created_at": "2026-04-01T00:00:00+00:00",
        "updated_at": "2026-04-01T00:00:00+00:00",
        "examiner": {"name": "Alex", "organisation": "", "badge_id": ""},
        "scope": {
            "exam_type": "",
            "device_classes": [],
            "evidence_items": [],
            "agencies": [],
            "summary": "",
            "notes": "",
        },
    }
    (case_dir / CASE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    loaded = read_case(case_dir)
    # Migrated to current schema with an empty custody record. As the
    # schema version moves forward, this test follows: the point is
    # that older case.json files keep loading and pick up safe defaults
    # for every field added since.
    assert loaded.schema_version == 3
    assert loaded.custody == CustodyRecord()
    assert loaded.scope.primary_tool == ""
    assert loaded.name == "Legacy"


def test_custody_seal_tri_state_round_trips(tmp_path: Path) -> None:
    """seal_intact tolerates None / True / False without coercing to bool."""
    base = _make_case_with_custody()
    for value in (None, True, False):
        case = dataclasses_replace_custody(base, seal_intact=value)
        target = create_case(
            workspace_root=tmp_path / f"seal-{value}",
            case=case,
        )
        loaded = read_case(target)
        assert loaded.custody.seal_intact is value


def dataclasses_replace_custody(case: Case, *, seal_intact: bool | None) -> Case:
    """Helper: mutate just the seal_intact field on a frozen Case."""
    return dataclasses.replace(
        case,
        custody=dataclasses.replace(case.custody, seal_intact=seal_intact),
    )


def test_unknown_future_schema_version_raises(tmp_path: Path) -> None:
    case = _make_case()
    target = create_case(workspace_root=tmp_path, case=case)
    payload = json.loads((target / CASE_FILENAME).read_text(encoding="utf-8"))
    payload["schema_version"] = 99
    (target / CASE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StorageError, match="newer"):
        read_case(target)
