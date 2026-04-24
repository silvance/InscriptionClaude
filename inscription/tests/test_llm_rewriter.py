"""StepRewriter: end-to-end with a fake LLMClient."""

from __future__ import annotations

import json

import pytest

from inscription.llm.client import LLMRequestError
from inscription.llm.rewriter import StepRewriter
from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.steps import generate_steps
from inscription.storage import SessionRepository


class _FakeClient:
    """Stand-in for :class:`LLMClient`; returns a canned content string."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, str]] = []

    def chat(self, *, system: str, user: str, **_kwargs: object) -> str:
        self.calls.append((system, user))
        return self.content


class _ExplodingClient:
    def chat(self, *, system: str, user: str, **_kwargs: object) -> str:
        msg = "connection refused"
        raise LLMRequestError(msg)


def _seed_one_click(repo: SessionRepository) -> int:
    resolved = repo.add_resolved_element(
        ResolvedElement(id=None, name="Save", control_type="Button", confidence=0.9, method="uia")
    )
    event = repo.append_event(
        kind=EventKind.CLICK,
        occurred_at=utcnow(),
        button="left",
        x=1,
        y=1,
        window_title="Notepad",
        process_name="notepad.exe",
        resolved_element_id=resolved.id,
    )
    assert event.id is not None
    return event.id


def test_rewriter_replaces_steps_from_llm_response(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="LLM")
    try:
        eid = _seed_one_click(repo)
        content = json.dumps({"steps": [{"text": "Save the document.", "source_event_ids": [eid]}]})
        rewriter = StepRewriter(repository=repo, client=_FakeClient(content))
        steps = rewriter.rewrite()

        assert len(steps) == 1
        assert steps[0].text == "Save the document."
        assert steps[0].source_event_ids == (eid,)
        assert steps[0].manual_edit is False
    finally:
        repo.close()


def test_rewriter_preserves_manual_edits(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Edits")
    try:
        eid = _seed_one_click(repo)

        # Simulate an earlier rule-based generation + manual edit.
        generate_steps(repo)
        initial = repo.list_steps()[0]
        assert initial.id is not None
        repo.update_step_text(initial.id, "Custom human text")

        # LLM suggests different text; the human edit should win.
        content = json.dumps({"steps": [{"text": "Robot text.", "source_event_ids": [eid]}]})
        steps = StepRewriter(repository=repo, client=_FakeClient(content)).rewrite()

        assert len(steps) == 1
        assert steps[0].text == "Custom human text"
        assert steps[0].manual_edit is True
    finally:
        repo.close()


def test_rewriter_surfaces_client_failure(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Boom")
    try:
        _seed_one_click(repo)
        rewriter = StepRewriter(repository=repo, client=_ExplodingClient())
        with pytest.raises(LLMRequestError):
            rewriter.rewrite()
    finally:
        repo.close()


def test_rewriter_noop_on_empty_session(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Empty")
    try:
        client = _FakeClient("should not be called")
        rewriter = StepRewriter(repository=repo, client=client)
        steps = rewriter.rewrite()
        assert steps == []
        assert client.calls == []
    finally:
        repo.close()


def test_rewriter_picks_last_screenshot_for_merged_step(tmp_path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Merge")
    try:
        shot_a = repo.add_screenshot(
            relative_path="screenshots/a.png",
            captured_at=utcnow(),
            width=1,
            height=1,
        )
        shot_b = repo.add_screenshot(
            relative_path="screenshots/b.png",
            captured_at=utcnow(),
            width=1,
            height=1,
        )
        e1 = repo.append_event(
            kind=EventKind.CLICK,
            button="left",
            x=1,
            y=1,
            screenshot_id=shot_a.id,
        )
        e2 = repo.append_event(
            kind=EventKind.CLICK,
            button="left",
            x=2,
            y=2,
            screenshot_id=shot_b.id,
        )
        assert e1.id is not None
        assert e2.id is not None

        content = json.dumps(
            {
                "steps": [
                    {"text": "Merged step.", "source_event_ids": [e1.id, e2.id]},
                ]
            }
        )
        steps = StepRewriter(repository=repo, client=_FakeClient(content)).rewrite()

        # Last-event-with-a-screenshot wins.
        assert steps[0].screenshot_id == shot_b.id
    finally:
        repo.close()
