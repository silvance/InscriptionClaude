"""Suggestion generator: matched playbooks -> SuggestionsDocument."""

from __future__ import annotations

from caseguide.case_reader import CaseScope
from caseguide.generator import generate_suggestions
from caseguide.playbooks import PlaybookMatcher, load_playbooks


def test_generate_for_axiom_ci_case_picks_axiom_variants() -> None:
    matcher = PlaybookMatcher(load_playbooks())
    scope = CaseScope(
        exam_type="CI investigation",
        primary_tool="axiom",
        device_classes=["windows-laptop"],
        evidence_items=["E01 image"],
    )
    doc = generate_suggestions(scope=scope, matcher=matcher)

    by_id = {s.id: s for s in doc.suggestions}
    assert "verify-image-hash" in by_id
    assert "axiom-ci-processing" in by_id
    assert "xways-rvs-processing" not in by_id

    # The verify-image-hash AXIOM variant should be in use, not the
    # generic body — confirms the tool wiring reaches the suggestions.
    assert "AXIOM Process" in by_id["verify-image-hash"].action


def test_generate_for_xways_case_picks_xways_variants() -> None:
    matcher = PlaybookMatcher(load_playbooks())
    scope = CaseScope(
        primary_tool="xways",
        evidence_items=["E01 image"],
    )
    doc = generate_suggestions(scope=scope, matcher=matcher)

    by_id = {s.id: s for s in doc.suggestions}
    assert "xways-rvs-processing" in by_id
    assert "axiom-ci-processing" not in by_id
    assert "Refine Volume Snapshot" in by_id["xways-rvs-processing"].action


def test_generate_priorities_sort_required_first() -> None:
    matcher = PlaybookMatcher(load_playbooks())
    scope = CaseScope(
        exam_type="CI",
        primary_tool="axiom",
        evidence_items=["E01 image"],
    )
    doc = generate_suggestions(scope=scope, matcher=matcher)
    priorities = [s.priority for s in doc.suggestions]
    # Required entries come before recommended ones.
    last_required = max(
        (i for i, p in enumerate(priorities) if p == "required"), default=-1
    )
    first_recommended = min(
        (i for i, p in enumerate(priorities) if p == "recommended"), default=len(priorities)
    )
    assert last_required < first_recommended


def test_generate_records_matched_playbook_ids() -> None:
    matcher = PlaybookMatcher(load_playbooks())
    scope = CaseScope(primary_tool="axiom", evidence_items=["E01 image"])
    doc = generate_suggestions(scope=scope, matcher=matcher)
    assert "verify-image-hash" in doc.playbooks
    assert "axiom-ci-processing" not in doc.playbooks  # exam_type didn't match


def test_generate_scope_summary_falls_back_to_summary_when_no_structured_fields() -> None:
    scope = CaseScope(summary="Free-form intake summary line.")
    doc = generate_suggestions(scope=scope, matcher=PlaybookMatcher([]))
    assert "Free-form" in doc.scope_summary
