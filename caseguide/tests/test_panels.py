"""Smoke tests for the scope + suggestions panels."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from caseguide.case_reader import CaseHandle, CaseScope
from caseguide.model import PRIORITY_REQUIRED, Suggestion
from caseguide.ui.scope_panel import ScopePanel
from caseguide.ui.suggestions_panel import SuggestionsPanel


def test_scope_panel_renders_a_case(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = ScopePanel()
    qtbot.addWidget(panel)
    handle = CaseHandle(
        name="Demo",
        case_reference="DM-1",
        examiner_name="Alex",
        scope=CaseScope(
            exam_type="CI",
            primary_tool="axiom",
            device_classes=["windows-laptop"],
            evidence_items=["E01 image"],
        ),
    )
    panel.show_case(handle, case_dir="/cases/demo")
    # Just confirm it didn't crash; visible-text checks would couple
    # the test to layout decisions that aren't load-bearing.
    panel.clear()


def test_suggestions_panel_round_trips_set_and_get(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    inputs = [
        Suggestion(id="a", action="Action A", priority=PRIORITY_REQUIRED),
        Suggestion(id="b", action="Action B", category="processing"),
    ]
    panel.set_suggestions(inputs)
    out = panel.suggestions()
    assert [s.id for s in out] == ["a", "b"]
    assert out[0].priority == PRIORITY_REQUIRED


def test_suggestions_panel_add_creates_a_new_row(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_suggestions([])
    panel._on_add()
    assert len(panel.suggestions()) == 1


def test_suggestions_panel_remove_deletes_selected(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_suggestions([
        Suggestion(id="a", action="A"),
        Suggestion(id="b", action="B"),
    ])
    panel._list.setCurrentRow(0)
    panel._on_remove()
    out = panel.suggestions()
    assert [s.id for s in out] == ["b"]


def test_suggestions_panel_move_swaps_neighbours(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_suggestions([
        Suggestion(id="a", action="A"),
        Suggestion(id="b", action="B"),
        Suggestion(id="c", action="C"),
    ])
    panel._list.setCurrentRow(2)
    panel._on_move(-1)
    assert [s.id for s in panel.suggestions()] == ["a", "c", "b"]
