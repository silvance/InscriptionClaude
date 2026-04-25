"""Integrity verification: clean / mismatched / missing / unhashed."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from inscription.model import utcnow
from inscription.storage import SessionRepository
from inscription.verify import verify_session_integrity

if TYPE_CHECKING:
    from pathlib import Path


def _stage_screenshot(repo: SessionRepository, *, name: str, body: bytes) -> str:
    """Write a PNG into the session's screenshots/ and register it.

    Returns the relative path so the test can mutate the file on disk.
    """
    rel = f"screenshots/{name}"
    target = repo.session.root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    repo.add_screenshot(
        relative_path=rel,
        captured_at=utcnow(),
        width=1,
        height=1,
        sha256=hashlib.sha256(body).hexdigest(),
    )
    return rel


def test_verify_clean_session(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Clean")
    try:
        _stage_screenshot(repo, name="a.png", body=b"first-png-bytes")
        _stage_screenshot(repo, name="b.png", body=b"second-png-bytes")
        result = verify_session_integrity(repo)
    finally:
        repo.close()

    assert result.total_checked == 2
    assert result.ok == 2
    assert result.is_clean is True
    assert not result.mismatched
    assert not result.missing
    assert not result.unhashed


def test_verify_detects_mismatched_screenshot(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Tampered")
    try:
        rel = _stage_screenshot(repo, name="a.png", body=b"original")
        # Mutate the file on disk after registration.
        (repo.session.root / rel).write_bytes(b"tampered-with-bytes")
        result = verify_session_integrity(repo)
    finally:
        repo.close()

    assert result.total_checked == 1
    assert result.ok == 0
    assert len(result.mismatched) == 1
    assert result.mismatched[0].relative_path == rel
    assert result.is_clean is False


def test_verify_detects_missing_screenshot(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Missing")
    try:
        rel = _stage_screenshot(repo, name="a.png", body=b"will-be-deleted")
        (repo.session.root / rel).unlink()
        result = verify_session_integrity(repo)
    finally:
        repo.close()

    assert result.missing == [rel]
    assert result.is_clean is False


def test_verify_flags_unhashed_rows_as_warnings(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Legacy")
    try:
        rel = "screenshots/legacy.png"
        target = repo.session.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"legacy-without-stored-hash")
        # Register without a sha256 — the very-early-alpha case.
        repo.add_screenshot(
            relative_path=rel,
            captured_at=utcnow(),
            width=1,
            height=1,
            sha256="",
        )
        result = verify_session_integrity(repo)
    finally:
        repo.close()

    assert result.unhashed == [rel]
    # Unhashed rows are warnings, not failures.
    assert result.is_clean is True
    assert result.has_warnings is True
