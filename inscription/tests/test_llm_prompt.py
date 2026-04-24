"""Prompt builder and response parser."""

from __future__ import annotations

import json

import pytest

from inscription.llm.client import LLMResponseError
from inscription.llm.prompt import build_user_prompt, parse_response
from inscription.model import DraftStep, EventKind, RawEvent, ResolvedElement, utcnow


def _event(
    *,
    event_id: int,
    kind: EventKind = EventKind.CLICK,
    resolved_id: int | None = None,
    window: str = "Notepad",
    process: str = "notepad.exe",
) -> RawEvent:
    return RawEvent(
        id=event_id,
        sequence=event_id,
        occurred_at=utcnow(),
        kind=kind,
        button="left" if kind is EventKind.CLICK else None,
        x=0,
        y=0,
        window_title=window,
        process_name=process,
        resolved_element_id=resolved_id,
    )


def test_build_user_prompt_contains_events_and_manual_edits() -> None:
    events = [
        _event(event_id=1, resolved_id=10),
        _event(event_id=2, kind=EventKind.KEY_PRESS),
    ]
    resolved = {
        10: ResolvedElement(
            id=10,
            name="Save",
            control_type="Button",
            confidence=0.9,
            method="uia",
            owner_process_name="notepad.exe",
        ),
    }
    existing = [
        DraftStep(
            id=1,
            sequence=1,
            text="Manually edited thing",
            source_event_ids=(1,),
            manual_edit=True,
        ),
        DraftStep(
            id=2,
            sequence=2,
            text="Auto thing",
            source_event_ids=(2,),
            manual_edit=False,
        ),
    ]
    prompt = build_user_prompt(
        session_name="Demo",
        events=events,
        resolved_by_id=resolved,
        existing_steps=existing,
    )

    assert "Demo" in prompt
    # Events appear with their IDs so the model can cite them back.
    assert '"id": 1' in prompt
    assert '"id": 2' in prompt
    # Resolved element surfaced.
    assert '"name": "Save"' in prompt
    assert '"control_type": "Button"' in prompt
    # Only manual-edit steps appear in the manual_edits block.
    assert "Manually edited thing" in prompt
    assert "Auto thing" not in prompt


def test_parse_response_accepts_plain_json() -> None:
    body = json.dumps({"steps": [{"text": "Click Save.", "source_event_ids": [1, 2]}]})
    out = parse_response(body, valid_event_ids={1, 2})
    assert len(out) == 1
    assert out[0].text == "Click Save."
    assert out[0].source_event_ids == (1, 2)


def test_parse_response_strips_markdown_fences() -> None:
    body = '```json\n{"steps": [{"text": "x", "source_event_ids": [7]}]}\n```'
    out = parse_response(body, valid_event_ids={7})
    assert out[0].text == "x"


def test_parse_response_drops_steps_with_no_known_ids() -> None:
    body = json.dumps(
        {
            "steps": [
                {"text": "Keeper.", "source_event_ids": [1]},
                {"text": "Ghost.", "source_event_ids": [999]},
            ]
        }
    )
    out = parse_response(body, valid_event_ids={1, 2})
    assert [s.text for s in out] == ["Keeper."]


def test_parse_response_rejects_missing_steps_key() -> None:
    with pytest.raises(LLMResponseError, match="missing top-level"):
        parse_response('{"foo": 1}', valid_event_ids={1})


def test_parse_response_rejects_non_array_steps() -> None:
    with pytest.raises(LLMResponseError, match="must be an array"):
        parse_response('{"steps": "nope"}', valid_event_ids={1})


def test_parse_response_rejects_zero_usable_steps() -> None:
    # Every step references an unknown id → all filtered out.
    body = json.dumps({"steps": [{"text": "x", "source_event_ids": [42]}]})
    with pytest.raises(LLMResponseError, match="zero usable"):
        parse_response(body, valid_event_ids={1, 2})


def test_parse_response_rejects_invalid_json() -> None:
    with pytest.raises(LLMResponseError, match="not valid JSON"):
        parse_response("this is not json", valid_event_ids={1})
