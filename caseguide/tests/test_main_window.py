"""Smoke test: the main window constructs without crashing."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from caseguide.ui.main_window import MainWindow


def test_main_window_constructs(qtbot) -> None:  # type: ignore[no-untyped-def]
    win = MainWindow(auto_show=False)
    qtbot.addWidget(win)
    assert win.windowTitle().startswith("CaseGuide")
