"""Smoke tests requiring a running Qt application.

Relies on the pytest-qt ``qtbot`` fixture, which manages a ``QApplication``
for the test session.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("pytestqt")

from inscription.ui.main_window import MainWindow
from inscription.version import __version__


@pytest.mark.gui
def test_main_window_constructs(qtbot: Any) -> None:
    window = MainWindow(auto_start_controller=False)
    qtbot.addWidget(window)
    assert __version__ in window.windowTitle()


@pytest.mark.gui
def test_main_window_menu_structure(qtbot: Any) -> None:
    window = MainWindow(auto_start_controller=False)
    qtbot.addWidget(window)

    titles = {action.text() for action in window.menuBar().actions()}
    assert "&File" in titles
    assert "&Edit" in titles
    assert "&View" in titles
    assert "&Help" in titles


@pytest.mark.gui
def test_main_window_has_status_bar(qtbot: Any) -> None:
    window = MainWindow(auto_start_controller=False)
    qtbot.addWidget(window)
    assert window.statusBar() is not None
    assert window.statusBar().currentMessage() == "Ready"
