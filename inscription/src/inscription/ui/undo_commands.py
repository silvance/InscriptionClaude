"""Undo / redo commands for the workspace step editor.

Built on Qt's :class:`QUndoStack` + :class:`QUndoCommand` so the Edit
menu's Undo / Redo entries auto-update their text ("Undo Edit step
3"), pick up Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z by default, and
coalesce consecutive text edits via :meth:`mergeWith`.

Two flavours of command live here:

- **In-place inverse** for cheap operations (text edit, suppress
  toggle, evidentiary toggle, reorder). The command stores the
  pre-mutation field values and the redo / undo paths each call a
  small repository setter.
- **Snapshot-and-restore** for structural changes (merge, split,
  append, regenerate, AI rewrite). The command snapshots the full
  step list before the change and restores it via
  :meth:`SessionRepository.replace_steps` on undo. ``replace_steps``
  re-creates rows so step ids change after an undo of these
  operations -- nothing user-visible depends on step ids and the
  workspace reloads from the repo, so the operator just sees the
  prior state restored.

The :class:`Workspace` protocol below is the minimum interface the
workspace widget has to implement so the commands can refresh the
UI without dragging the full :class:`SessionWorkspaceWidget` type
into a unit test.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from inscription.model import DraftStep
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)


class Workspace(Protocol):
    """Minimum surface the commands need to refresh the editor on undo/redo."""

    def reload(self) -> None: ...


#: Coalesce consecutive text edits of the same step within this many
#: milliseconds into one undo entry. Without coalescing every keystroke
#: would be its own undo step, which is unusable.
_TEXT_EDIT_COALESCE_MS = 600

#: Stable id used by Qt to know when two ``EditStepFieldsCommand``
#: instances may be merged. Qt only merges commands with the same id.
_EDIT_STEP_FIELDS_ID = 1


class _StepCommandBase(QUndoCommand):
    """Common scaffolding: hold the repo + workspace refs, log on apply."""

    def __init__(
        self,
        *,
        repository: SessionRepository,
        workspace: Workspace,
        text: str,
    ) -> None:
        super().__init__(text)
        self._repository = repository
        self._workspace = workspace


class EditStepFieldsCommand(_StepCommandBase):
    """Edit a step's action and/or result text.

    Coalesces consecutive edits to the same step (typing keeps
    extending one undo entry rather than creating one per keystroke).
    """

    def __init__(
        self,
        *,
        repository: SessionRepository,
        workspace: Workspace,
        step_id: int,
        before_action: str,
        before_result: str,
        before_manual_edit: bool,
        after_action: str,
        after_result: str,
    ) -> None:
        super().__init__(
            repository=repository,
            workspace=workspace,
            text=f"Edit step {step_id}",
        )
        self._step_id = step_id
        self._before_action = before_action
        self._before_result = before_result
        self._before_manual_edit = before_manual_edit
        # Mutable so mergeWith() can extend the "after" state as the user
        # keeps typing in the same field.
        self._after_action = after_action
        self._after_result = after_result

    def id(self) -> int:
        return _EDIT_STEP_FIELDS_ID

    def mergeWith(self, other: QUndoCommand) -> bool:  # noqa: N802 - Qt API
        if not isinstance(other, EditStepFieldsCommand):
            return False
        if other._step_id != self._step_id:
            return False
        # Extend our "after" state to include the newer edit. The "before"
        # state stays put -- one undo restores the pre-merge state.
        self._after_action = other._after_action
        self._after_result = other._after_result
        return True

    def redo(self) -> None:
        self._repository.update_step_fields(
            self._step_id,
            action=self._after_action,
            result=self._after_result,
            manual_edit=True,
        )
        self._workspace.reload()

    def undo(self) -> None:
        self._repository.update_step_fields(
            self._step_id,
            action=self._before_action,
            result=self._before_result,
            manual_edit=self._before_manual_edit,
        )
        self._workspace.reload()


class SetStepSuppressedCommand(_StepCommandBase):
    """Toggle a step's suppression flag."""

    def __init__(
        self,
        *,
        repository: SessionRepository,
        workspace: Workspace,
        step_id: int,
        before: bool,
        after: bool,
    ) -> None:
        verb = "Suppress" if after else "Unsuppress"
        super().__init__(
            repository=repository,
            workspace=workspace,
            text=f"{verb} step {step_id}",
        )
        self._step_id = step_id
        self._before = before
        self._after = after

    def redo(self) -> None:
        self._repository.set_step_suppressed(self._step_id, suppressed=self._after)
        self._workspace.reload()

    def undo(self) -> None:
        self._repository.set_step_suppressed(self._step_id, suppressed=self._before)
        self._workspace.reload()


class SetStepEvidentiaryCommand(_StepCommandBase):
    """Toggle a step's evidentiary flag (no UI reload -- inline checkbox)."""

    def __init__(
        self,
        *,
        repository: SessionRepository,
        workspace: Workspace,
        step_id: int,
        before: bool,
        after: bool,
    ) -> None:
        verb = "Mark" if after else "Unmark"
        super().__init__(
            repository=repository,
            workspace=workspace,
            text=f"{verb} step {step_id} as evidentiary",
        )
        self._step_id = step_id
        self._before = before
        self._after = after

    def redo(self) -> None:
        self._repository.set_step_evidentiary(self._step_id, evidentiary=self._after)
        self._workspace.reload()

    def undo(self) -> None:
        self._repository.set_step_evidentiary(self._step_id, evidentiary=self._before)
        self._workspace.reload()


class ReorderStepsCommand(_StepCommandBase):
    """Reassign the ``sequence`` column to match an explicit ordering."""

    def __init__(
        self,
        *,
        repository: SessionRepository,
        workspace: Workspace,
        before_order: list[int],
        after_order: list[int],
    ) -> None:
        super().__init__(
            repository=repository,
            workspace=workspace,
            text="Reorder steps",
        )
        self._before = list(before_order)
        self._after = list(after_order)

    def redo(self) -> None:
        self._repository.reorder_steps(self._after)
        self._repository.flush_manifest()
        self._workspace.reload()

    def undo(self) -> None:
        self._repository.reorder_steps(self._before)
        self._repository.flush_manifest()
        self._workspace.reload()


class SnapshotAndReplaceCommand(_StepCommandBase):
    """Snapshot the full step list, run an arbitrary mutation, restore on undo.

    Used for structural changes the repo can't trivially invert in
    place: merge, split, append-from-suggestion, regenerate, AI
    rewrite. The command snapshots every draft step before the
    mutation runs and restores them via ``replace_steps`` on undo.

    ``replace_steps`` re-creates rows so step ids change after undo
    of these operations. Nothing user-visible depends on step ids
    (the workspace reloads from the repo on every command), so the
    operator just sees the prior state.

    The mutation is supplied as a callable rather than baked in so
    each call site can name its operation and pass any args without
    a per-operation subclass. ``mutate`` runs once on the first
    redo; subsequent redos re-snapshot the post-mutation state and
    restore it (handles the typical Edit -> Undo -> Redo flow).
    """

    def __init__(
        self,
        *,
        repository: SessionRepository,
        workspace: Workspace,
        text: str,
        mutate: object,  # callable(): None  -- type via Protocol below
    ) -> None:
        super().__init__(
            repository=repository,
            workspace=workspace,
            text=text,
        )
        self._mutate = mutate
        self._before: list[DraftStep] | None = None
        self._after: list[DraftStep] | None = None
        self._first_run = True

    def redo(self) -> None:
        if self._first_run:
            self._before = self._repository.list_steps(include_suppressed=True)
            self._mutate()  # type: ignore[operator]
            self._after = self._repository.list_steps(include_suppressed=True)
            self._first_run = False
        else:
            assert self._after is not None
            self._repository.replace_steps(list(self._after))
        self._repository.flush_manifest()
        self._workspace.reload()

    def undo(self) -> None:
        assert self._before is not None
        self._repository.replace_steps(list(self._before))
        self._repository.flush_manifest()
        self._workspace.reload()
