"""Integration tests for the full stack.

Drives :class:`CaseController` programmatically, verifies case lifecycle
and step capture land correctly in SQLite + on disk. No user dialogs;
we test controller methods directly.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("pytestqt")

from inscription.cases.models import StepKind
from inscription.storage import CaseRepository
from inscription.storage.repository import list_cases
from inscription.ui.case_workspace import CaseWorkspaceWidget

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.gui
def test_create_open_capture_reopen_flow(qtbot: Any, tmp_path: Path) -> None:
    """Exercise the full Phase 1 happy path end-to-end.

    Creates a case, fires some captures through the repository + engine
    stack (without dialogs), closes the case, then reopens and verifies
    the persisted steps are all present.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # --- Create and capture.
    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-9000",
        title="Integration flow",
        examiner="James",
    )
    session = repo.start_session()
    assert session.id is not None

    # Simulate three captures by directly appending steps (the engine path
    # is covered in test_capture.py; here we focus on case lifecycle).
    for i in range(3):
        repo.append_step(
            session_id=session.id,
            kind=StepKind.HOTKEY_CAPTURE,
            title=f"Step {i + 1}",
            screenshot_path=f"screenshots/step-{i + 1}.png",
        )

    repo.close()

    # --- Verify case appears in the listing.
    manifests = list_cases(workspace)
    assert len(manifests) == 1
    assert manifests[0].case_number == "HSV-2026-9000"
    assert manifests[0].step_count == 3

    # --- Reopen and verify steps persist.
    with CaseRepository.open_existing(
        workspace_root=workspace, case_number="HSV-2026-9000"
    ) as reopened:
        steps = reopened.list_steps()
        assert len(steps) == 3
        assert [s.title for s in steps] == ["Step 1", "Step 2", "Step 3"]


@pytest.mark.gui
def test_workspace_ui_appends_steps(qtbot: Any, tmp_path: Path) -> None:
    """Bind a repository to the workspace widget and append a step via the UI."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-9002",
        title="UI flow",
        examiner="James",
    )
    try:
        session = repo.start_session()
        assert session.id is not None

        widget = CaseWorkspaceWidget()
        qtbot.addWidget(widget)
        widget.set_repository(repo)

        step = repo.append_step(
            session_id=session.id,
            kind=StepKind.HOTKEY_CAPTURE,
            title="First step",
        )
        widget.append_step(step)

        # Let Qt process events so the list updates.
        qtbot.wait(50)
        # The step list widget exposes count via its underlying QListWidget.
        assert widget._list.count() == 1
    finally:
        repo.close()


def test_repository_survives_rapid_appends(tmp_path: Path) -> None:
    """Stress the repository lock with many sequential appends."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo = CaseRepository.create(
        workspace_root=workspace,
        case_number="HSV-2026-9001",
        title="Stress",
        examiner="James",
    )
    try:
        session = repo.start_session()
        assert session.id is not None

        start = time.monotonic()
        for i in range(200):
            repo.append_step(
                session_id=session.id,
                kind=StepKind.HOTKEY_CAPTURE,
                title=f"s{i}",
            )
        elapsed = time.monotonic() - start

        steps = repo.list_steps(session.id)
        assert len(steps) == 200
        assert [s.sequence for s in steps] == list(range(1, 201))
        # Sanity: 200 inserts should be well under a second on any machine.
        assert elapsed < 5.0, f"200 appends took {elapsed:.2f}s"
    finally:
        repo.close()
