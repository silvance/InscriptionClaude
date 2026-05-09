"""End-to-end tests for the workspace undo/redo commands.

Drives each command class against a real :class:`SessionRepository`
+ a fake :class:`Workspace` (records ``reload`` calls but doesn't
need a Qt widget). Each test exercises the full do → undo → redo
round-trip so a future repository refactor can't silently break the
inverse without one of these tests catching it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytest.importorskip("pytestqt")

from inscription.model import DraftStep, EventKind, ResolvedElement
from inscription.storage import SessionRepository
from inscription.ui.undo_commands import (
    EditStepFieldsCommand,
    ReorderStepsCommand,
    SetStepEvidentiaryCommand,
    SetStepSuppressedCommand,
    SnapshotAndReplaceCommand,
    Workspace,
)


class _FakeWorkspace:
    """Minimal Workspace stand-in that just records ``reload`` calls."""

    def __init__(self) -> None:
        self.reloads = 0

    def reload(self) -> None:
        self.reloads += 1


def _seed_two_steps(repo: SessionRepository) -> tuple[int, int]:
    """Seed two click events + a default-generated step list, return the
    two step ids in sequence order."""
    resolved = repo.add_resolved_element(
        ResolvedElement(id=None, name="Save", control_type="Button", confidence=0.9, method="uia")
    )
    e1 = repo.append_event(
        kind=EventKind.CLICK, button="left", x=1, y=1,
        window_title="Notepad", process_name="notepad.exe",
        resolved_element_id=resolved.id,
    )
    e2 = repo.append_event(
        kind=EventKind.CLICK, button="left", x=2, y=2,
        window_title="Notepad", process_name="notepad.exe",
        resolved_element_id=resolved.id,
    )
    assert e1.id is not None
    assert e2.id is not None
    saved = repo.replace_steps([
        DraftStep(
            id=None, sequence=0, action="Click Save",
            source_event_ids=(e1.id,),
        ),
        DraftStep(
            id=None, sequence=0, action="Click Save again",
            source_event_ids=(e2.id,),
        ),
    ])
    return cast("int", saved[0].id), cast("int", saved[1].id)


def test_edit_step_fields_round_trip(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="EditUndo")
    try:
        sid, _ = _seed_two_steps(repo)
        workspace = _FakeWorkspace()
        before = repo.get_step(sid)
        assert before is not None
        cmd = EditStepFieldsCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            step_id=sid,
            before_action=before.action,
            before_result=before.result,
            before_manual_edit=before.manual_edit,
            after_action="Edited action",
            after_result="Edited result",
        )

        cmd.redo()
        edited = repo.get_step(sid)
        assert edited is not None
        assert edited.action == "Edited action"
        assert edited.result == "Edited result"
        assert edited.manual_edit is True

        cmd.undo()
        restored = repo.get_step(sid)
        assert restored is not None
        assert restored.action == before.action
        assert restored.result == before.result
        assert restored.manual_edit == before.manual_edit
    finally:
        repo.close()


def test_edit_step_fields_coalesces_consecutive_edits(tmp_path: Path) -> None:
    """mergeWith() should fold two consecutive edits to the same step
    into a single undo entry. This is what makes Ctrl+Z usable while
    typing."""
    repo = SessionRepository.create(workspace_root=tmp_path, name="EditCoalesce")
    try:
        sid, _ = _seed_two_steps(repo)
        workspace = _FakeWorkspace()
        before = repo.get_step(sid)
        assert before is not None

        first = EditStepFieldsCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            step_id=sid,
            before_action=before.action,
            before_result=before.result,
            before_manual_edit=before.manual_edit,
            after_action="A",
            after_result="",
        )
        second = EditStepFieldsCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            step_id=sid,
            before_action="A",
            before_result="",
            before_manual_edit=True,
            after_action="AB",
            after_result="",
        )
        # mergeWith returns True; the merged command should restore to
        # the FIRST command's "before" state, not the second's.
        assert first.mergeWith(second) is True
        first.redo()
        assert repo.get_step(sid).action == "AB"  # type: ignore[union-attr]
        first.undo()
        assert repo.get_step(sid).action == before.action  # type: ignore[union-attr]
    finally:
        repo.close()


def test_edit_step_fields_refuses_merge_outside_coalesce_window(tmp_path: Path) -> None:
    """An edit made well after the coalesce window has lapsed should
    NOT merge into the previous command -- the operator expects one
    Ctrl+Z to undo the most recent edit, not a 10-minute-old one."""
    repo = SessionRepository.create(workspace_root=tmp_path, name="EditWindow")
    try:
        sid, _ = _seed_two_steps(repo)
        workspace = _FakeWorkspace()
        before = repo.get_step(sid)
        assert before is not None

        first = EditStepFieldsCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            step_id=sid,
            before_action=before.action,
            before_result=before.result,
            before_manual_edit=before.manual_edit,
            after_action="A",
            after_result="",
        )
        # Push the first command's "last extended at" stamp 10 minutes
        # into the past so the second edit looks like a separate op.
        first._last_extended_at -= 600.0
        second = EditStepFieldsCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            step_id=sid,
            before_action="A",
            before_result="",
            before_manual_edit=True,
            after_action="AB",
            after_result="",
        )
        assert first.mergeWith(second) is False
    finally:
        repo.close()


def test_set_step_suppressed_round_trip(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Suppress")
    try:
        sid, _ = _seed_two_steps(repo)
        workspace = _FakeWorkspace()
        cmd = SetStepSuppressedCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            step_id=sid,
            before=False,
            after=True,
        )
        cmd.redo()
        assert repo.get_step(sid).suppressed is True  # type: ignore[union-attr]
        cmd.undo()
        assert repo.get_step(sid).suppressed is False  # type: ignore[union-attr]
    finally:
        repo.close()


def test_set_step_evidentiary_round_trip(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Evid")
    try:
        sid, _ = _seed_two_steps(repo)
        workspace = _FakeWorkspace()
        cmd = SetStepEvidentiaryCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            step_id=sid,
            before=False,
            after=True,
        )
        cmd.redo()
        assert repo.get_step(sid).evidentiary is True  # type: ignore[union-attr]
        cmd.undo()
        assert repo.get_step(sid).evidentiary is False  # type: ignore[union-attr]
    finally:
        repo.close()


def test_reorder_steps_round_trip(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Reorder")
    try:
        a, b = _seed_two_steps(repo)
        workspace = _FakeWorkspace()
        cmd = ReorderStepsCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            before_order=[a, b],
            after_order=[b, a],
        )
        cmd.redo()
        ids_after = [s.id for s in repo.list_steps(include_suppressed=True)]
        assert ids_after == [b, a]
        cmd.undo()
        ids_restored = [s.id for s in repo.list_steps(include_suppressed=True)]
        assert ids_restored == [a, b]
    finally:
        repo.close()


def test_snapshot_and_replace_undoes_merge(tmp_path: Path) -> None:
    """Merge is a structural change; SnapshotAndReplaceCommand should
    capture the pre-merge step list and restore it on undo."""
    repo = SessionRepository.create(workspace_root=tmp_path, name="MergeUndo")
    try:
        a, b = _seed_two_steps(repo)
        workspace = _FakeWorkspace()
        actions_before = [s.action for s in repo.list_steps(include_suppressed=True)]

        def mutate() -> None:
            repo.merge_steps(primary_id=a, other_id=b)

        cmd = SnapshotAndReplaceCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            text="Merge",
            mutate=mutate,
        )
        cmd.redo()
        # After merge, only one step remains.
        assert len(repo.list_steps(include_suppressed=True)) == 1
        cmd.undo()
        # The original two steps are back -- ids may differ (replace_steps
        # re-creates rows) but actions are restored.
        actions_after = [s.action for s in repo.list_steps(include_suppressed=True)]
        assert actions_after == actions_before
    finally:
        repo.close()


def test_snapshot_and_replace_redo_uses_post_state(tmp_path: Path) -> None:
    """After undo, redo should re-apply the mutation. Re-running the
    callable would double-apply (e.g. merge an already-merged row);
    the command captures the post-mutation state on first redo and
    restores it via replace_steps on subsequent redos."""
    repo = SessionRepository.create(workspace_root=tmp_path, name="MergeRedo")
    try:
        a, b = _seed_two_steps(repo)
        workspace = _FakeWorkspace()

        def mutate() -> None:
            repo.merge_steps(primary_id=a, other_id=b)

        cmd = SnapshotAndReplaceCommand(
            repository=repo,
            workspace=cast("Workspace", workspace),
            text="Merge",
            mutate=mutate,
        )
        cmd.redo()
        merged_actions = [s.action for s in repo.list_steps(include_suppressed=True)]
        cmd.undo()
        cmd.redo()
        assert [s.action for s in repo.list_steps(include_suppressed=True)] == merged_actions
    finally:
        repo.close()
