"""LLM prompt parsing + SuggestionsRefiner end-to-end with a fake client."""

from __future__ import annotations

import json

import pytest
from suite_common.llm import LLMResponseError

from caseguide.case_reader import CaseScope
from caseguide.llm.augment import SuggestionsRefiner
from caseguide.llm.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_response,
)
from caseguide.model import PRIORITY_REQUIRED, Suggestion


class _FakeClient:
    """Stand-in for LLMClient. Returns a canned content string."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, str]] = []

    def chat(self, *, system: str, user: str, **_kwargs: object) -> str:
        self.calls.append((system, user))
        return self.content


def _drafts() -> list[Suggestion]:
    return [
        Suggestion(
            id="verify-image-hash",
            action="Compute the SHA-256 of the acquired image.",
            priority=PRIORITY_REQUIRED,
            category="verification",
        ),
        Suggestion(
            id="axiom-ci-processing",
            action="Run AXIOM Process with every category enabled.",
            priority=PRIORITY_REQUIRED,
            category="processing",
        ),
    ]


def test_system_prompt_anchors_the_role() -> None:
    """Regression guard: refining-not-inventing is in the prompt."""
    text = SYSTEM_PROMPT.lower()
    assert "refine" in text
    assert "do not invent" in text or "never invent" in text


def test_system_prompt_names_the_forensic_context() -> None:
    """The exam context (digital forensics, disclosure / court risk)
    should land early so the model treats output as procedural log
    rather than casual chat."""
    head = SYSTEM_PROMPT[:400].lower()
    assert "forensic" in head
    assert "examiner" in head


def test_user_prompt_carries_scope_and_drafts() -> None:
    scope = CaseScope(exam_type="CI", primary_tool="axiom")
    prompt = build_user_prompt(scope=scope, drafts=_drafts())
    assert '"primary_tool": "axiom"' in prompt
    assert "verify-image-hash" in prompt


def test_parse_response_accepts_plain_json() -> None:
    body = json.dumps(
        {
            "suggestions": [
                {
                    "id": "verify-image-hash",
                    "action": "Verify SHA-256 against the AXIOM acquisition log.",
                    "priority": "required",
                    "category": "verification",
                    "expected_result": "Hash matches.",
                    "rationale": "",
                    "references": [],
                    "depends_on": [],
                    "source_id": "verify-image-hash",
                }
            ]
        }
    )
    out = parse_response(body)
    assert len(out) == 1
    assert out[0].action == "Verify SHA-256 against the AXIOM acquisition log."
    assert out[0].source_id == "verify-image-hash"


def test_parse_response_strips_markdown_fences() -> None:
    body = (
        "```json\n"
        '{"suggestions": [{"id": "x", "action": "y", "priority": "required", '
        '"category": "", "source_id": "x"}]}\n'
        "```"
    )
    out = parse_response(body)
    assert out[0].action == "y"


def test_parse_response_rejects_non_object_root() -> None:
    with pytest.raises(LLMResponseError):
        parse_response("[1, 2, 3]")


def test_parse_response_rejects_missing_suggestions_key() -> None:
    with pytest.raises(LLMResponseError, match="missing top-level"):
        parse_response('{"foo": []}')


def test_parse_response_rejects_zero_usable_suggestions() -> None:
    body = json.dumps({"suggestions": [{"id": "no-action"}]})
    with pytest.raises(LLMResponseError, match="zero usable"):
        parse_response(body)


def test_refiner_round_trips_drafts_through_fake_client() -> None:
    refined_payload = json.dumps(
        {
            "suggestions": [
                {
                    "id": "verify-image-hash",
                    "action": (
                        "Verify the SHA-256 against the AXIOM "
                        "acquisition log; record in Activity Log."
                    ),
                    "priority": "required",
                    "category": "verification",
                    "source_id": "verify-image-hash",
                }
            ]
        }
    )
    refiner = SuggestionsRefiner(client=_FakeClient(refined_payload))
    out = refiner.refine(scope=CaseScope(primary_tool="axiom"), drafts=_drafts())

    assert len(out) == 1
    assert out[0].id == "verify-image-hash"
    assert "AXIOM" in out[0].action


def test_refiner_returns_empty_for_empty_drafts() -> None:
    refiner = SuggestionsRefiner(client=_FakeClient("should not be called"))
    out = refiner.refine(scope=CaseScope(), drafts=[])
    assert out == []


def test_refiner_preserves_completed_drafts_unchanged() -> None:
    """Completed entries skip the LLM and re-appear after the refined list."""
    payload = json.dumps(
        {
            "suggestions": [
                {
                    "id": "axiom-ci-processing",
                    "action": "Refined active step.",
                    "priority": "required",
                    "category": "processing",
                    "source_id": "axiom-ci-processing",
                }
            ]
        }
    )
    fake = _FakeClient(payload)
    drafts = _drafts()
    drafts[0] = Suggestion(
        id="verify-image-hash",
        action="Verify SHA-256.",
        priority=PRIORITY_REQUIRED,
        category="verification",
        completed=True,
    )
    refiner = SuggestionsRefiner(client=fake)
    out = refiner.refine(scope=CaseScope(primary_tool="axiom"), drafts=drafts)

    assert [s.id for s in out] == ["axiom-ci-processing", "verify-image-hash"]
    assert out[1].completed is True
    # The completed entry must not have been included in the prompt
    # — that's the whole point of the skip.
    assert "verify-image-hash" not in fake.calls[0][1]


def test_refiner_returns_completed_only_when_no_active_drafts() -> None:
    fake = _FakeClient("should not be called")
    drafts = [
        Suggestion(
            id="done",
            action="Already done.",
            priority=PRIORITY_REQUIRED,
            completed=True,
        ),
    ]
    refiner = SuggestionsRefiner(client=fake)
    out = refiner.refine(scope=CaseScope(), drafts=drafts)
    assert [s.id for s in out] == ["done"]
    assert fake.calls == []


def test_refiner_falls_through_source_id_for_new_entries() -> None:
    """LLM-added suggestions get their ``source_id`` carried as the row id."""
    payload = json.dumps(
        {
            "suggestions": [
                {
                    "id": "manual-1",
                    "action": "New scope-specific step the playbooks didn't cover.",
                    "priority": "recommended",
                    "category": "analysis",
                    "source_id": "manual-1",
                }
            ]
        }
    )
    refiner = SuggestionsRefiner(client=_FakeClient(payload))
    out = refiner.refine(scope=CaseScope(), drafts=_drafts())
    assert out[0].id == "manual-1"
