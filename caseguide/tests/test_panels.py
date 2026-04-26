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


def test_suggestions_panel_mark_complete_toggles_state(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_suggestions([Suggestion(id="a", action="Verify hash.")])
    panel._list.setCurrentRow(0)

    panel._on_toggle_completed()
    out = panel.suggestions()
    assert out[0].completed is True
    assert out[0].completed_at is not None

    panel._on_toggle_completed()
    out = panel.suggestions()
    assert out[0].completed is False
    assert out[0].completed_at is None


def test_suggestions_panel_edits_round_trip_across_row_switches(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Locks in the QSignalBlocker refactor.

    Programmatic ``setText`` / ``setCurrentIndex`` calls inside
    ``_populate_editor`` used to be filtered through a manual
    ``_suppress_signals`` flag; the swap to ``QSignalBlocker`` should
    be invisible. This test forces the path that flag was guarding:
    select row A → user edits the action → switch to row B → switch
    back. If the blocker leaks, switching writes the *previous* row's
    field text back into the new row's suggestion.
    """
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_suggestions([
        Suggestion(id="a", action="A original", category="cat-a"),
        Suggestion(id="b", action="B original", category="cat-b"),
    ])
    panel._list.setCurrentRow(0)
    # Simulate a user edit: change the action text. This must propagate
    # to suggestions[0] but not to suggestions[1] when we switch rows.
    panel._action_edit.setPlainText("A edited")
    panel._on_field_changed()
    panel._list.setCurrentRow(1)
    # When the editor populates with row B's values, the blocker must
    # suppress textChanged so the populate doesn't fire _on_field_changed
    # and overwrite row B with row A's edited text.
    out = panel.suggestions()
    assert out[0].action == "A edited"
    assert out[1].action == "B original"
    assert out[1].category == "cat-b"

    # Switch back to A; populate must not regress A's edit.
    panel._list.setCurrentRow(0)
    out = panel.suggestions()
    assert out[0].action == "A edited"


def test_suggestions_panel_render_clear_does_not_emit_phantom_selection(  # type: ignore[no-untyped-def]
    qtbot,
) -> None:
    """``_render`` clears + repopulates the QListWidget; the selection
    signal that fires mid-clear must not crash on the now-empty model."""
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    # Drive a render that goes from 3 rows to 0 rows, exercising the
    # clear-then-rebuild path with the blocker around _list.clear().
    panel.set_suggestions([
        Suggestion(id="a", action="A"),
        Suggestion(id="b", action="B"),
        Suggestion(id="c", action="C"),
    ])
    panel._list.setCurrentRow(1)
    panel.set_suggestions([])
    # Empty editor visible, no exceptions.
    assert panel._editor_stack.currentIndex() == 0
    assert panel.suggestions() == []
