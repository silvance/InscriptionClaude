"""Prompt builder and response parser."""

from __future__ import annotations

import json

import pytest
from suite_common.llm import LLMResponseError

from inscription.llm.prompt import SYSTEM_PROMPT, build_user_prompt, parse_response
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
            action="Manually edited thing",
            source_event_ids=(1,),
            manual_edit=True,
        ),
        DraftStep(
            id=2,
            sequence=2,
            action="Auto thing",
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


def test_system_prompt_forbids_invented_actions() -> None:
    """Regression guard against the model fabricating scrolling / tab
    navigation when the input timeline contains only clicks."""
    text = SYSTEM_PROMPT.lower()
    assert "never invent actions" in text or "do not fabricate" in text or "do not invent" in text
    # Mention the specific failure modes we observed in the wild so the
    # rule can't quietly drift away from them.
    assert "scroll" in text
    assert "tab" in text


def test_system_prompt_anchors_forensic_role_up_front() -> None:
    """The role and exam context should land in the first ~400 chars so
    smaller models don't get distracted by output-format instructions
    before they know what they're doing."""
    head = SYSTEM_PROMPT[:400].lower()
    assert "forensic" in head
    assert "examiner" in head


def test_system_prompt_lists_recognisable_tool_names() -> None:
    """If the model doesn't know "Magnet AXIOM" is a forensic tool, it
    won't render window titles like "Magnet AXIOM Process" with the
    right vocabulary. Pin a representative subset so a future tidy-up
    can't quietly drop them."""
    text = SYSTEM_PROMPT.lower()
    assert "magnet axiom" in text or "axiom" in text
    assert "x-ways" in text
    assert "cellebrite" in text


def test_system_prompt_warns_against_fabricated_button_paths() -> None:
    """Smaller models love to invent menu paths that "sound right"
    (Tools → Verify Hashes, Files → Add Evidence). The prompt has
    a hard rule against that; keep it."""
    text = SYSTEM_PROMPT.lower()
    assert "do not invent" in text
    # The "button path / feature name" framing is what trips small
    # models up most -- keep the specific phrasing pinned.
    assert "button path" in text or "menu path" in text or "feature name" in text


def test_parse_response_accepts_plain_json() -> None:
    body = json.dumps(
        {
            "steps": [
                {
                    "action": "Click Save.",
                    "result": "File saved.",
                    "source_event_ids": [1, 2],
                }
            ]
        }
    )
    out = parse_response(body, valid_event_ids={1, 2})
    assert len(out) == 1
    assert out[0].action == "Click Save."
    assert out[0].result == "File saved."
    assert out[0].source_event_ids == (1, 2)


def test_parse_response_strips_markdown_fences() -> None:
    body = '```json\n{"steps": [{"action": "x", "result": "", "source_event_ids": [7]}]}\n```'
    out = parse_response(body, valid_event_ids={7})
    assert out[0].action == "x"
    assert out[0].result == ""


def test_parse_response_accepts_legacy_text_field() -> None:
    """Old JSON payloads using {"text": ...} still parse as action-only."""
    body = json.dumps({"steps": [{"text": "Legacy step.", "source_event_ids": [1]}]})
    out = parse_response(body, valid_event_ids={1})
    assert out[0].action == "Legacy step."
    assert out[0].result == ""


def test_parse_response_drops_steps_with_no_known_ids() -> None:
    body = json.dumps(
        {
            "steps": [
                {"action": "Keeper.", "result": "", "source_event_ids": [1]},
                {"action": "Ghost.", "result": "", "source_event_ids": [999]},
            ]
        }
    )
    out = parse_response(body, valid_event_ids={1, 2})
    assert [s.action for s in out] == ["Keeper."]


def test_parse_response_rejects_missing_steps_key() -> None:
    with pytest.raises(LLMResponseError, match="missing top-level"):
        parse_response('{"foo": 1}', valid_event_ids={1})


def test_parse_response_rejects_non_array_steps() -> None:
    with pytest.raises(LLMResponseError, match="must be an array"):
        parse_response('{"steps": "nope"}', valid_event_ids={1})


def test_parse_response_rejects_zero_usable_steps() -> None:
    # Every step references an unknown id → all filtered out.
    body = json.dumps(
        {"steps": [{"action": "x", "result": "", "source_event_ids": [42]}]}
    )
    with pytest.raises(LLMResponseError, match="zero usable"):
        parse_response(body, valid_event_ids={1, 2})


def test_parse_response_rejects_invalid_json() -> None:
    with pytest.raises(LLMResponseError, match="did not return JSON"):
        parse_response("this is not json at all", valid_event_ids={1})


def test_parse_response_recovers_json_from_prose_preamble() -> None:
    """Smaller models routinely prepend a sentence of commentary even
    when the prompt forbids it. The parser must extract the JSON
    object that follows so the rewrite still lands."""
    body = (
        "Sure! Here is the JSON object you asked for:\n\n"
        '{"steps": [{"action": "Open the case folder.", '
        '"result": "", "source_event_ids": [1]}]}\n\n'
        "Let me know if you'd like me to adjust anything."
    )
    out = parse_response(body, valid_event_ids={1})
    assert len(out) == 1
    assert out[0].action == "Open the case folder."


def test_parse_response_recovers_json_with_braces_in_strings() -> None:
    """The brace-balance walker must ignore braces inside string
    literals so a JSON object whose action text contains a literal
    ``{`` doesn't confuse the extractor."""
    body = (
        'Here is the result: {"steps": [{"action": '
        '"Type \\"{ \\\\\\"k\\\\\\": 1 }\\" into the field.", '
        '"result": "", "source_event_ids": [1]}]} done.'
    )
    out = parse_response(body, valid_event_ids={1})
    assert len(out) == 1
    assert "{" in out[0].action


def test_parse_response_error_message_points_at_settings_for_pure_prose() -> None:
    """When the model returns purely prose with no JSON, the error
    message should hint at Settings → LLM (the user can swap the
    model from there) rather than a bare "invalid JSON" line."""
    body = (
        "The user is interacting with a sequence of applications and "
        "processes, which suggests a workflow involving research, "
        "software installation/setup, and potentially data analysis."
    )
    with pytest.raises(LLMResponseError, match="Settings"):
        parse_response(body, valid_event_ids={1})
