"""End-to-end tests for CaseRepository.

These tests exercise the full storage stack: slug, schema init, manifest,
lockfile, mutations. No Qt, no filesystem outside tmp_path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from inscription.cases.models import StepKind
from inscription.storage import (
    CaseAlreadyExistsError,
    CaseLockedError,
    CaseNotFoundError,
    CaseRepository,
)
from inscription.storage.manifest import read_manifest
from inscription.storage.repository import list_cases

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------- fixtures


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


# ---------------------------------------------------------------- create


def test_create_case_produces_expected_layout(workspace: Path) -> None:
    with CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0317",
        title="Test case",
        examiner="James",
    ) as repo:
        case_root = workspace / "HSV-2026-0317"
        assert case_root.is_dir()
        assert (case_root / "case.db").is_file()
        assert (case_root / "manifest.json").is_file()
        assert (case_root / "screenshots").is_dir()
        assert (case_root / ".inscription" / "version").read_text() == "1"
        assert (case_root / ".inscription" / "case.lock").is_file()
        assert repo.case.info.case_number == "HSV-2026-0317"
        assert repo.case.info.examiner == "James"


def test_create_rejects_duplicate_case(workspace: Path) -> None:
    CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0001",
        title="First",
        examiner="James",
    ).close()
    with pytest.raises(CaseAlreadyExistsError):
        CaseRepository.create(
            workspace_root=workspace,
            case_number="HSV-2026-0001",
            title="Dupe",
            examiner="James",
        )


# ---------------------------------------------------------------- open


def test_open_missing_case_raises(workspace: Path) -> None:
    with pytest.raises(CaseNotFoundError):
        CaseRepository.open_existing(workspace_root=workspace, case_number="HSV-2026-9999")


def test_reopen_preserves_data(workspace: Path) -> None:
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0002",
        title="Reopen",
        examiner="James",
    )
    session = repo.start_session()
    assert session.id is not None
    step = repo.append_step(
        session_id=session.id,
        kind=StepKind.HOTKEY_CAPTURE,
        title="Step A",
        screenshot_path="screenshots/a.png",
    )
    assert step.id is not None
    repo.close()

    with CaseRepository.open_existing(
        workspace_root=workspace, case_number="HSV-2026-0002"
    ) as reopened:
        steps = reopened.list_steps()
        assert len(steps) == 1
        assert steps[0].title == "Step A"
        assert steps[0].sequence == 1


# ---------------------------------------------------------------- steps


def test_sequence_auto_increments_within_session(workspace: Path) -> None:
    with CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0003",
        title="Seq",
        examiner="James",
    ) as repo:
        s = repo.start_session()
        assert s.id is not None
        a = repo.append_step(session_id=s.id, kind=StepKind.HOTKEY_CAPTURE)
        b = repo.append_step(session_id=s.id, kind=StepKind.HOTKEY_CAPTURE)
        c = repo.append_step(session_id=s.id, kind=StepKind.MANUAL_NOTE)
        assert [a.sequence, b.sequence, c.sequence] == [1, 2, 3]


def test_sequence_is_per_session(workspace: Path) -> None:
    with CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0004",
        title="Multi-session",
        examiner="James",
    ) as repo:
        s1 = repo.start_session()
        assert s1.id is not None
        a = repo.append_step(session_id=s1.id, kind=StepKind.HOTKEY_CAPTURE)
        repo.end_session(s1.id)

        s2 = repo.start_session()
        assert s2.id is not None
        b = repo.append_step(session_id=s2.id, kind=StepKind.HOTKEY_CAPTURE)
        assert a.sequence == 1
        assert b.sequence == 1


def test_update_step_text(workspace: Path) -> None:
    with CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0005",
        title="Edit",
        examiner="James",
    ) as repo:
        s = repo.start_session()
        assert s.id is not None
        step = repo.append_step(session_id=s.id, kind=StepKind.MANUAL_NOTE, title="old")
        assert step.id is not None
        repo.update_step_text(step.id, title="new", body_markdown="notes here")
        steps = repo.list_steps()
        assert steps[0].title == "new"
        assert steps[0].body_markdown == "notes here"


# ---------------------------------------------------------------- manifest


def test_manifest_written_on_close(workspace: Path) -> None:
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0006",
        title="Manifest check",
        examiner="James",
    )
    s = repo.start_session()
    assert s.id is not None
    repo.append_step(session_id=s.id, kind=StepKind.HOTKEY_CAPTURE)
    repo.append_step(session_id=s.id, kind=StepKind.HOTKEY_CAPTURE)
    repo.close()

    manifest = read_manifest(workspace / "HSV-2026-0006" / "manifest.json")
    assert manifest.step_count == 2
    assert manifest.case_number == "HSV-2026-0006"
    assert manifest.title == "Manifest check"


def test_list_cases_returns_all_manifests(workspace: Path) -> None:
    for n in range(3):
        CaseRepository.create(
            workspace_root=workspace,
            case_number=f"HSV-2026-010{n}",
            title=f"Case {n}",
            examiner="James",
        ).close()

    manifests = list_cases(workspace)
    assert len(manifests) == 3
    assert {m.case_number for m in manifests} == {
        "HSV-2026-0100",
        "HSV-2026-0101",
        "HSV-2026-0102",
    }


def test_list_cases_tolerates_missing_workspace(tmp_path: Path) -> None:
    assert list_cases(tmp_path / "nonexistent") == []


# ---------------------------------------------------------------- locking


def test_double_open_rejected(workspace: Path) -> None:
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0200",
        title="Locked",
        examiner="James",
    )
    try:
        with pytest.raises(CaseLockedError):
            CaseRepository.open_existing(workspace_root=workspace, case_number="HSV-2026-0200")
    finally:
        repo.close()


def test_stale_lock_reclaimed(workspace: Path) -> None:
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-0201",
        title="Stale",
        examiner="James",
    )
    repo.close()
    # Simulate a crashed previous process by writing a nonsense PID.
    lock = workspace / "HSV-2026-0201" / ".inscription" / "case.lock"
    lock.write_text("999999", encoding="utf-8")

    # Should succeed by reclaiming the stale lock.
    with CaseRepository.open_existing(
        workspace_root=workspace, case_number="HSV-2026-0201"
    ) as reopened:
        assert reopened.case.info.case_number == "HSV-2026-0201"
