"""Tests for the paths module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inscription import paths

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_app_dir_is_absolute() -> None:
    assert paths.APP_DIR.is_absolute()


def test_log_dir_is_under_app_dir() -> None:
    assert paths.LOG_DIR.is_relative_to(paths.APP_DIR)


def test_workspace_dir_is_under_app_dir() -> None:
    assert paths.WORKSPACE_DIR.is_relative_to(paths.APP_DIR)


def test_cache_dir_is_under_app_dir() -> None:
    assert paths.CACHE_DIR.is_relative_to(paths.APP_DIR)


def test_ensure_dirs_creates_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_dir = tmp_path / "Inscription"
    monkeypatch.setattr(paths, "APP_DIR", app_dir)
    monkeypatch.setattr(paths, "LOG_DIR", app_dir / "logs")
    monkeypatch.setattr(paths, "WORKSPACE_DIR", app_dir / "workspace")
    monkeypatch.setattr(paths, "CACHE_DIR", app_dir / "cache")

    paths.ensure_dirs()

    assert app_dir.is_dir()
    assert (app_dir / "logs").is_dir()
    assert (app_dir / "workspace").is_dir()
    assert (app_dir / "cache").is_dir()


def test_ensure_dirs_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_dir = tmp_path / "Inscription"
    monkeypatch.setattr(paths, "APP_DIR", app_dir)
    monkeypatch.setattr(paths, "LOG_DIR", app_dir / "logs")
    monkeypatch.setattr(paths, "WORKSPACE_DIR", app_dir / "workspace")
    monkeypatch.setattr(paths, "CACHE_DIR", app_dir / "cache")

    paths.ensure_dirs()
    paths.ensure_dirs()  # must not raise

    assert app_dir.is_dir()
