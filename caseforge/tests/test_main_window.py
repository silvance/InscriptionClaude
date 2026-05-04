"""Smoke test: the main window constructs without crashing."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from caseforge.config import Config
from caseforge.model import ExaminerIdentity, ExamScope
from caseforge.ui import onboarding_dialog as ob_module
from caseforge.ui.main_window import MainWindow
from caseforge.ui.new_case_dialog import NewCaseDialog
from caseforge.ui.settings_dialog import SettingsDialog


def test_main_window_constructs(qtbot) -> None:  # type: ignore[no-untyped-def]
    win = MainWindow(auto_show=False)
    qtbot.addWidget(win)
    assert win.windowTitle().startswith("CaseForge")


def test_new_case_dialog_constructs(qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = NewCaseDialog(
        examiner_defaults=ExaminerIdentity(name="Alex", organisation="CCU"),
        scope_defaults=ExamScope(),
    )
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "New case"


def test_settings_dialog_constructs(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = Config(path=tmp_path / "cfg.ini")
    dialog = SettingsDialog(cfg)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Settings"


def test_maybe_show_onboarding_skips_when_flag_set(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Operator already onboarded: dialog must not appear on next launch."""
    cfg = Config(path=tmp_path / "cfg.ini")
    cfg.onboarding_completed = True
    win = MainWindow(auto_show=False, config=cfg)
    qtbot.addWidget(win)

    called = False

    def fake_exec(self: object) -> int:
        nonlocal called
        called = True
        return 0

    original = ob_module.OnboardingDialog.exec
    ob_module.OnboardingDialog.exec = fake_exec  # type: ignore[method-assign]
    try:
        win._maybe_show_onboarding()
    finally:
        ob_module.OnboardingDialog.exec = original  # type: ignore[method-assign]

    assert called is False


def test_maybe_show_onboarding_runs_when_flag_unset(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Fresh profile: dialog appears once."""
    cfg = Config(path=tmp_path / "cfg.ini")
    win = MainWindow(auto_show=False, config=cfg)
    qtbot.addWidget(win)

    called = False

    def fake_exec(self: object) -> int:
        nonlocal called
        called = True
        # Simulate the user hitting Skip so the flag flips.
        cfg.onboarding_completed = True
        return 1

    original = ob_module.OnboardingDialog.exec
    ob_module.OnboardingDialog.exec = fake_exec  # type: ignore[method-assign]
    try:
        win._maybe_show_onboarding()
    finally:
        ob_module.OnboardingDialog.exec = original  # type: ignore[method-assign]

    assert called is True
