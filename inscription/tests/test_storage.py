"""Session repository: create, persist, reopen, lock."""

from __future__ import annotations

import pytest

from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.storage import (
    SessionAlreadyExistsError,
    SessionLockedError,
    SessionNotFoundError,
    SessionRepository,
    list_sessions,
)


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
            )
        )
        assert stored.id is not None
        loaded = repo.get_resolved_element(stored.id)
        assert loaded is not None
        assert loaded.name == "OK"
        assert loaded.confidence == pytest.approx(0.9)
        assert loaded.bounding_rect == (100, 200, 150, 230)
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
