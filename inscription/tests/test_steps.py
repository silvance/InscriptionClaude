"""Step generation: raw events -> draft steps."""

from __future__ import annotations

from datetime import timedelta

from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.steps import StepGenerator, render_step_text
from inscription.storage import SessionRepository


def _append_click(
    repo: SessionRepository,
    *,
    when,
    resolved_id=None,
    window="App",
    screenshot_id=None,
):
    return repo.append_event(
        kind=EventKind.CLICK,
        occurred_at=when,
        button="left",
        x=10,
        y=10,
        window_title=window,
        process_name="app.exe",
        screenshot_id=screenshot_id,
        resolved_element_id=resolved_id,
    )


def test_render_step_text_prefers_uia_name() -> None:

    event = type(
        "E",
        (),
        {
            "kind": EventKind.CLICK,
            "key": None,
            "text": None,
            "window_title": "Settings",
            "button": "left",
        },
    )()
    resolved = ResolvedElement(
        id=1, name="Save", control_type="Button", confidence=0.9, method="uia"
    )
    rendered = render_step_text(event, resolved)  # type: ignore[arg-type]
    assert "Save" in rendered
    assert "Button" in rendered
    assert "Settings" in rendered


def test_generator_collapses_redundant_clicks(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Gen")
    try:
        resolved = repo.add_resolved_element(
            ResolvedElement(id=None, name="OK", control_type="Button", confidence=0.9, method="uia")
        )
        t0 = utcnow()
        _append_click(repo, when=t0, resolved_id=resolved.id)
        _append_click(repo, when=t0 + timedelta(milliseconds=300), resolved_id=resolved.id)
        # Third click after dedup window -> separate step
        _append_click(repo, when=t0 + timedelta(seconds=5), resolved_id=resolved.id)

        steps = StepGenerator(repo).regenerate()
        assert len(steps) == 2
        assert "OK" in steps[0].text
    finally:
        repo.close()


def test_generator_suppresses_window_focus_before_click(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Focus")
    try:
        t0 = utcnow()
        repo.append_event(
            kind=EventKind.WINDOW_FOCUS,
            occurred_at=t0,
            text="Target",
        )
        repo.append_event(
            kind=EventKind.CLICK,
            occurred_at=t0 + timedelta(milliseconds=200),
            button="left",
            x=5,
            y=5,
            window_title="Target",
        )
        steps = StepGenerator(repo).regenerate()
        assert len(steps) == 1
        assert "Target" in steps[0].text
    finally:
        repo.close()


def test_generator_preserves_manual_edits(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Edits")
    try:
        t0 = utcnow()
        _append_click(repo, when=t0)

        steps = StepGenerator(repo).regenerate()
        assert len(steps) == 1
        first = steps[0]
        assert first.id is not None

        repo.update_step_text(first.id, "Click the magical button")

        regenerated = StepGenerator(repo).regenerate()
        assert len(regenerated) == 1
        assert regenerated[0].text == "Click the magical button"
        assert regenerated[0].manual_edit is True
    finally:
        repo.close()
