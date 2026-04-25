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
                DraftStep(id=None, sequence=0, text="Click first.", source_event_ids=(e1,)),
                DraftStep(id=None, sequence=0, text="Click second.", source_event_ids=(e2,)),
            ]
        )
        assert saved[0].id is not None
        assert saved[1].id is not None
        merged = repo.merge_steps(primary_id=saved[0].id, other_id=saved[1].id)

        remaining = repo.list_steps()
        assert len(remaining) == 1
        assert remaining[0].id == saved[0].id
        assert remaining[0].source_event_ids == (e1, e2)
        assert remaining[0].text == "Click first. Click second."
        assert remaining[0].manual_edit is True
        assert merged.text == remaining[0].text
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
                    text="Combo step.",
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
            [DraftStep(id=None, sequence=0, text="Single.", source_event_ids=(e1,))]
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
            [DraftStep(id=None, sequence=0, text="Marked", source_event_ids=(e1.id,))]
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
                DraftStep(id=None, sequence=0, text="A", source_event_ids=(e1,)),
                DraftStep(id=None, sequence=0, text="B", source_event_ids=(e2,)),
                DraftStep(id=None, sequence=0, text="C", source_event_ids=(e3,)),
            ]
        )
        ids = [s.id for s in saved if s.id is not None]
        assert len(ids) == 3
        repo.reorder_steps([ids[2], ids[0], ids[1]])

        listed = repo.list_steps()
        assert [s.text for s in listed] == ["C", "A", "B"]
    finally:
        repo.close()
