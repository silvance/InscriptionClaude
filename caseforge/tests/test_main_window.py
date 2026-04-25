"""Smoke test: the main window constructs without crashing."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from caseforge.config import Config
from caseforge.model import ExaminerIdentity, ExamScope
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
