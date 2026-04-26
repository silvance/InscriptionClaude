"""Smoke tests for the read-only CaseGuide suggestions panel."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("pytestqt")

from inscription.caseguide_link import CaseguideSuggestion, suggestions_path
from inscription.ui.suggestions_panel import SuggestionsPanel

if TYPE_CHECKING:
    from pathlib import Path


def _write_payload(case_dir: Path, suggestions: list[dict[str, object]]) -> None:
    target = suggestions_path(case_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "scope_summary": "Demo scope.",
                "playbooks": [],
                "suggestions": suggestions,
            }
        ),
        encoding="utf-8",
    )


def test_panel_hidden_when_no_case_dir(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_case_dir(None)
    assert not panel.isVisible()


def test_panel_hidden_when_file_missing(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    case_dir = tmp_path / "case-no-file"
    case_dir.mkdir()
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_case_dir(case_dir)
    assert not panel.isVisible()


def test_panel_renders_suggestions_when_present(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    case_dir = tmp_path / "case-loaded"
    _write_payload(
        case_dir,
        [
            {
                "id": "verify-image-hash",
                "action": "Verify SHA-256.",
                "priority": "required",
                "expected_result": "Hash matches.",
            },
            {
                "id": "done-step",
                "action": "Already done.",
                "priority": "recommended",
                "completed": True,
                "completed_at": "2026-04-25T15:00:00+00:00",
            },
        ],
    )
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_case_dir(case_dir)
    panel.show()
    assert panel.isVisible()
    assert panel._list.count() == 2
    # First row is open, second is the completed one with strikeout font.
    first = panel._list.item(0)
    second = panel._list.item(1)
    assert first is not None
    assert second is not None
    assert not first.font().strikeOut()
    assert second.font().strikeOut()


def test_draft_button_emits_signal_when_session_open(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    case_dir = tmp_path / "case-draftable"
    _write_payload(
        case_dir,
        [
            {
                "id": "verify-image-hash",
                "action": "Verify SHA-256.",
                "priority": "required",
                "expected_result": "Hash matches.",
            },
        ],
    )
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_case_dir(case_dir)
    panel.set_session_open(open_=True)
    panel._list.setCurrentRow(0)

    received: list[CaseguideSuggestion] = []
    panel.draft_step_requested.connect(received.append)
    assert panel._draft_button.isEnabled()
    panel._draft_button.click()

    assert len(received) == 1
    assert received[0].id == "verify-image-hash"


def test_draft_button_disabled_without_open_session(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    case_dir = tmp_path / "case-no-session"
    _write_payload(
        case_dir,
        [{"id": "x", "action": "Y", "priority": "required"}],
    )
    panel = SuggestionsPanel()
    qtbot.addWidget(panel)
    panel.set_case_dir(case_dir)
    panel.set_session_open(open_=False)
    panel._list.setCurrentRow(0)
    assert not panel._draft_button.isEnabled()
