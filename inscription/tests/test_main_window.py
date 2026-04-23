"""Smoke test: the main window constructs without a session and without crashing."""

from __future__ import annotations

import pytest

from inscription.ui.main_window import MainWindow

pytest.importorskip("pytestqt")


def test_main_window_constructs_without_autostart(qtbot) -> None:  # type: ignore[no-untyped-def]
    win = MainWindow(auto_start_controller=False)
    qtbot.addWidget(win)
    assert win.windowTitle().startswith("Inscription")
