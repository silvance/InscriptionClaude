"""Paths module: resolution and directory creation."""

from __future__ import annotations

from inscription import paths


def test_app_dir_contains_app_name() -> None:
    assert paths.APP_NAME in str(paths.APP_DIR)


def test_ensure_dirs_is_idempotent(tmp_path, monkeypatch) -> None:
    app_dir = tmp_path / "app"
    monkeypatch.setattr(paths, "APP_DIR", app_dir)
    monkeypatch.setattr(paths, "LOG_DIR", app_dir / "logs")
    monkeypatch.setattr(paths, "WORKSPACE_DIR", app_dir / "workspace")
    monkeypatch.setattr(paths, "CACHE_DIR", app_dir / "cache")

    paths.ensure_dirs()
    paths.ensure_dirs()

    for sub in ("logs", "workspace", "cache"):
        assert (app_dir / sub).is_dir()
