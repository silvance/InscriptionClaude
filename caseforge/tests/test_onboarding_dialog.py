"""Tests for the first-run onboarding dialog and its Config wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from caseforge.config import Config
from caseforge.ui.onboarding_dialog import (
    OnboardingDialog,
    _default_visible_workspace,
    _suggested_examiner_name,
)

# ----------------------------------------------------- Config flag

def test_onboarding_completed_defaults_to_false(tmp_path: Path) -> None:
    cfg = Config(path=tmp_path / "cfg.ini")
    assert cfg.onboarding_completed is False


def test_onboarding_completed_round_trips(tmp_path: Path) -> None:
    cfg = Config(path=tmp_path / "cfg.ini")
    cfg.onboarding_completed = True
    cfg.sync()
    reloaded = Config(path=tmp_path / "cfg.ini")
    assert reloaded.onboarding_completed is True


def test_has_explicit_workspace_false_by_default(tmp_path: Path) -> None:
    cfg = Config(path=tmp_path / "cfg.ini")
    assert cfg.has_explicit_workspace is False


def test_has_explicit_workspace_true_after_set(tmp_path: Path) -> None:
    cfg = Config(path=tmp_path / "cfg.ini")
    cfg.workspace_root = tmp_path / "ws"
    assert cfg.has_explicit_workspace is True


# ----------------------------------------------------- Helpers

def test_default_visible_workspace_ends_in_caseforge() -> None:
    """The suggested path is always under CaseForge so cases stay grouped."""
    assert _default_visible_workspace().name == "CaseForge"


def test_suggested_examiner_name_returns_string() -> None:
    """We don't assert the exact value (depends on the test runner) but
    the helper must never raise — it's purely a pre-fill convenience."""
    result = _suggested_examiner_name()
    assert isinstance(result, str)


# ----------------------------------------------------- Dialog

def test_dialog_constructs_with_defaults(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    dialog = OnboardingDialog(cfg)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Welcome to CaseForge"


def test_dialog_prefills_existing_examiner_name(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    cfg.examiner_name = "Jordan Reyes"
    dialog = OnboardingDialog(cfg)
    qtbot.addWidget(dialog)
    assert dialog._name_edit.text() == "Jordan Reyes"


def test_dialog_prefills_existing_workspace(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    cfg.workspace_root = tmp_path / "explicit-ws"
    dialog = OnboardingDialog(cfg)
    qtbot.addWidget(dialog)
    assert dialog._workspace_edit.text() == str(tmp_path / "explicit-ws")


def test_save_persists_fields_and_sets_flag(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    dialog = OnboardingDialog(cfg)
    qtbot.addWidget(dialog)
    dialog._name_edit.setText("Sam Examiner")
    ws = tmp_path / "new-workspace"
    dialog._workspace_edit.setText(str(ws))
    dialog._on_save()
    assert cfg.examiner_name == "Sam Examiner"
    assert cfg.workspace_root == ws
    assert cfg.onboarding_completed is True
    assert ws.is_dir()


def test_save_with_empty_workspace_shows_error_and_keeps_flag_false(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    dialog = OnboardingDialog(cfg)
    qtbot.addWidget(dialog)
    dialog._workspace_edit.setText("")
    dialog._on_save()
    assert dialog._error_label.text()
    assert not dialog._error_label.isHidden()
    assert cfg.onboarding_completed is False


def test_skip_sets_flag_without_writing_other_fields(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    dialog = OnboardingDialog(cfg)
    qtbot.addWidget(dialog)
    # Operator typed something but then hit Skip — we should NOT persist
    # those values, only the "don't bother me again" flag.
    dialog._name_edit.setText("Should Not Persist")
    dialog._workspace_edit.setText(str(tmp_path / "should-not-create"))
    dialog._on_skip()
    assert cfg.examiner_name == ""
    assert cfg.has_explicit_workspace is False
    assert cfg.onboarding_completed is True
    assert not (tmp_path / "should-not-create").exists()


def test_save_with_unwritable_workspace_shows_error(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    dialog = OnboardingDialog(cfg)
    qtbot.addWidget(dialog)
    dialog._workspace_edit.setText(str(tmp_path / "ws"))

    def boom(self: Path, parents: bool = False, exist_ok: bool = False) -> None:
        raise OSError("nope")

    monkeypatch.setattr(Path, "mkdir", boom)
    dialog._on_save()
    assert dialog._error_label.text()
    assert not dialog._error_label.isHidden()
    assert cfg.onboarding_completed is False
