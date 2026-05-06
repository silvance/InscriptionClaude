"""Session repository: create, persist, reopen, lock."""

from __future__ import annotations

import pytest

from inscription.model import DraftStep, EventKind, ResolvedElement, utcnow
from inscription.storage import (
    SessionAlreadyExistsError,
    SessionLockedError,
    SessionNotFoundError,
    SessionRepository,
    list_sessions,
    locking,
)
from inscription.storage.errors import StorageError


def test_create_and_close(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Test Flow")
    try:
        assert repo.session.info.name == "Test Flow"
        assert repo.session.db_path.exists()
        assert repo.session.screenshots_dir.is_dir()
        assert repo.session.exports_dir.is_dir()
    finally:
        repo.close()


def test_create_rejects_duplicate_slug(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Dup")
    repo.close()
    with pytest.raises(SessionAlreadyExistsError):
        SessionRepository.create(workspace_root=tmp_path, name="Dup")


def test_reopen_reads_same_data(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Reopen Me")
    slug = repo.session.root.name
    event = repo.append_event(kind=EventKind.CLICK, x=10, y=20, button="left")
    assert event.sequence == 1
    repo.close()

    reopened = SessionRepository.open_existing(workspace_root=tmp_path, slug=slug)
    try:
        events = reopened.list_events()
        assert len(events) == 1
        assert events[0].kind is EventKind.CLICK
        assert events[0].x == 10
    finally:
        reopened.close()


def test_open_missing_raises(tmp_path) -> None:
    with pytest.raises(SessionNotFoundError):
        SessionRepository.open_existing(workspace_root=tmp_path, slug="missing")


def test_lockfile_prevents_second_open(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Locked")
    try:
        slug = repo.session.root.name
        with pytest.raises(SessionLockedError):
            SessionRepository.open_existing(workspace_root=tmp_path, slug=slug)
    finally:
        repo.close()


def test_lockfile_acquire_is_atomic(tmp_path) -> None:
    """Direct test of locking.acquire's O_CREAT|O_EXCL semantics.

    The previous implementation did exists() + later write_text(),
    so two parallel acquire() calls with the same path could both
    pass the existence check and both believe they hold the lock.
    With O_EXCL the second create fails immediately.
    """
    lock_path = tmp_path / "session.lock"
    locking.acquire(lock_path)
    try:
        # Second acquire on the same live lock must refuse rather than
        # silently overwrite the holder's PID.
        with pytest.raises(SessionLockedError):
            locking.acquire(lock_path)
    finally:
        locking.release(lock_path)


def test_list_sessions_returns_manifests(tmp_path) -> None:
    a = SessionRepository.create(workspace_root=tmp_path, name="Alpha")
    a.close()
    b = SessionRepository.create(workspace_root=tmp_path, name="Beta")
    b.close()
    listed = list_sessions(tmp_path)
    names = {m.name for _, m in listed}
    assert names == {"Alpha", "Beta"}


def test_screenshot_round_trip(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Shots")
    try:
        shot = repo.add_screenshot(
            relative_path="screenshots/x.png",
            captured_at=utcnow(),
            width=100,
            height=50,
            sha256="deadbeef",
        )
        assert shot.id is not None
        loaded = repo.get_screenshot(shot.id)
        assert loaded is not None
        assert loaded.sha256 == "deadbeef"
        assert loaded.width == 100
    finally:
        repo.close()


def test_resolved_element_round_trip(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Elements")
    try:
        stored = repo.add_resolved_element(
            ResolvedElement(
                id=None,
                name="OK",
                control_type="Button",
                confidence=0.9,
                method="uia",
                bounding_rect=(100, 200, 150, 230),
                owner_process_name="notepad.exe",
            )
        )
        assert stored.id is not None
        loaded = repo.get_resolved_element(stored.id)
        assert loaded is not None
        assert loaded.name == "OK"
        assert loaded.confidence == pytest.approx(0.9)
        assert loaded.bounding_rect == (100, 200, 150, 230)
        assert loaded.owner_process_name == "notepad.exe"
    finally:
        repo.close()


def test_resolved_element_without_bounding_rect_round_trips(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="NoRect")
    try:
        stored = repo.add_resolved_element(
            ResolvedElement(id=None, name="x", confidence=0.3, method="foreground-only")
        )
        assert stored.id is not None
        loaded = repo.get_resolved_element(stored.id)
        assert loaded is not None
        assert loaded.bounding_rect is None
    finally:
        repo.close()


# ----------------------------------------------------- step editing helpers


def _seed_three_clicks(repo: SessionRepository) -> list[int]:
    """Append three CLICK events and return their event ids."""
    ids = []
    for x in (1, 2, 3):
        event = repo.append_event(kind=EventKind.CLICK, x=x, y=x, button="left")
        assert event.id is not None
        ids.append(event.id)
    return ids


def test_merge_steps_concatenates_source_events_and_text(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Merge")
    try:
        e1, e2, _ = _seed_three_clicks(repo)
        saved = repo.replace_steps(
            [
                DraftStep(id=None, sequence=0, action="Click first.", source_event_ids=(e1,)),
                DraftStep(
                    id=None,
                    sequence=0,
                    action="Click second.",
                    result="It worked.",
                    source_event_ids=(e2,),
                ),
            ]
        )
        assert saved[0].id is not None
        assert saved[1].id is not None
        merged = repo.merge_steps(primary_id=saved[0].id, other_id=saved[1].id)

        remaining = repo.list_steps()
        assert len(remaining) == 1
        assert remaining[0].id == saved[0].id
        assert remaining[0].source_event_ids == (e1, e2)
        assert remaining[0].action == "Click first. Click second."
        assert remaining[0].result == "It worked."
        assert remaining[0].manual_edit is True
        assert merged.action == remaining[0].action
        assert merged.result == remaining[0].result
    finally:
        repo.close()


def test_split_step_partitions_first_event_off(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Split")
    try:
        e1, e2, e3 = _seed_three_clicks(repo)
        saved = repo.replace_steps(
            [
                DraftStep(
                    id=None,
                    sequence=0,
                    action="Combo step.",
                    source_event_ids=(e1, e2, e3),
                )
            ]
        )
        assert saved[0].id is not None
        first, second = repo.split_step(saved[0].id)

        assert first.source_event_ids == (e1,)
        assert second.source_event_ids == (e2, e3)
        assert first.manual_edit is True
        assert second.manual_edit is True
        assert first.id == saved[0].id

        listed = repo.list_steps()
        assert [s.id for s in listed] == [first.id, second.id]
        assert listed[0].sequence < listed[1].sequence
    finally:
        repo.close()


def test_split_step_refuses_when_only_one_source_event(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="NoSplit")
    try:
        (e1,) = _seed_three_clicks(repo)[:1]
        saved = repo.replace_steps(
            [DraftStep(id=None, sequence=0, action="Single.", source_event_ids=(e1,))]
        )
        assert saved[0].id is not None
        with pytest.raises(StorageError, match="cannot split"):
            repo.split_step(saved[0].id)
    finally:
        repo.close()


def test_evidentiary_flag_round_trips(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Evidence")
    try:
        e1 = repo.append_event(kind=EventKind.CLICK, x=1, y=1, button="left")
        assert e1.id is not None
        saved = repo.replace_steps(
            [DraftStep(id=None, sequence=0, action="Marked", source_event_ids=(e1.id,))]
        )
        sid = saved[0].id
        assert sid is not None
        assert saved[0].evidentiary is False  # default

        repo.set_step_evidentiary(sid, evidentiary=True)
        listed = repo.list_steps()
        assert listed[0].evidentiary is True

        repo.set_step_evidentiary(sid, evidentiary=False)
        listed = repo.list_steps()
        assert listed[0].evidentiary is False
    finally:
        repo.close()


def test_reorder_steps_updates_sequence(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Reorder")
    try:
        e1, e2, e3 = _seed_three_clicks(repo)
        saved = repo.replace_steps(
            [
                DraftStep(id=None, sequence=0, action="A", source_event_ids=(e1,)),
                DraftStep(id=None, sequence=0, action="B", source_event_ids=(e2,)),
                DraftStep(id=None, sequence=0, action="C", source_event_ids=(e3,)),
            ]
        )
        ids = [s.id for s in saved if s.id is not None]
        assert len(ids) == 3
        repo.reorder_steps([ids[2], ids[0], ids[1]])

        listed = repo.list_steps()
        assert [s.action for s in listed] == ["C", "A", "B"]
    finally:
        repo.close()


# ----------------------------------------------------- transaction rollback

def test_transaction_rolls_back_on_exception(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Mid-write failure must NOT leak partial state into the next write.

    Regression guard for the field-quality-review finding: the old
    pattern was ``with self._lock: ...self._commit(what=...)`` with no
    rollback on exception. If a write inside the block raised, SQLite's
    implicit transaction was left open with the partial work pending;
    the next call to a write method's _commit() would commit that
    leftover state alongside its own work. The new ``_transaction``
    context manager rolls back on exception so the DB is unchanged
    after a failed partial write.
    """
    repo = SessionRepository.create(workspace_root=tmp_path, name="Rollback")
    try:
        repo.replace_steps([
            DraftStep(
                id=None, sequence=0, action="A", result="",
                source_event_ids=(), screenshot_id=None,
            ),
            DraftStep(
                id=None, sequence=0, action="B", result="",
                source_event_ids=(), screenshot_id=None,
            ),
        ])
        baseline = [(s.action, s.result) for s in repo.list_steps()]
        assert baseline == [("A", ""), ("B", "")]

        # Drive _transaction directly: do a destructive DELETE inside
        # the block and then raise. Without rollback, the DELETE would
        # be committed by the *next* successful write method's commit.
        # With rollback, the rows survive.
        # PT012 wants a single statement inside pytest.raises, but
        # this regression test genuinely needs to run multiple lines
        # inside the _transaction block (DELETE then raise) to show
        # the rollback semantics.
        def provoke_rollback() -> None:
            with repo._transaction(what="synthetic-failure"):
                repo._conn.execute("DELETE FROM draft_steps")
                msg = "synthetic mid-write failure"
                raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="synthetic"):
            provoke_rollback()

        # Subsequent unrelated successful write must NOT carry the
        # rolled-back DELETE forward.
        repo.set_step_evidentiary(
            repo.list_steps()[0].id or 0, evidentiary=True
        )

        after = [(s.action, s.result) for s in repo.list_steps()]
        assert after == baseline, (
            "Failed _transaction leaked partial state into the DB; "
            "rollback regression."
        )
    finally:
        repo.close()
