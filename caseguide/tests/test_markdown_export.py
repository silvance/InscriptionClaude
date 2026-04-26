"""Markdown checklist renderer."""

from __future__ import annotations

from datetime import UTC, datetime

from caseguide.case_reader import CaseHandle, CaseScope
from caseguide.markdown_export import render_markdown
from caseguide.model import (
    PRIORITY_OPTIONAL,
    PRIORITY_RECOMMENDED,
    PRIORITY_REQUIRED,
    Suggestion,
    SuggestionsDocument,
)


def _doc(*, suggestions: list[Suggestion]) -> SuggestionsDocument:
    return SuggestionsDocument(
        generated_at=datetime(2026, 4, 26, 14, 30, tzinfo=UTC),
        scope_summary="CSAM possession; Win11 laptop.",
        playbooks=["verify-image-hash", "axiom-ci-processing"],
        suggestions=suggestions,
    )


def test_renders_unchecked_and_checked_boxes() -> None:
    doc = _doc(
        suggestions=[
            Suggestion(
                id="verify-image-hash",
                action="Verify SHA-256.",
                priority=PRIORITY_REQUIRED,
                completed=True,
                completed_at=datetime(2026, 4, 26, 15, 0, tzinfo=UTC),
            ),
            Suggestion(id="next-step", action="Pending step.", priority=PRIORITY_REQUIRED),
        ],
    )
    md = render_markdown(doc)
    assert "- [x] **Verify SHA-256.**" in md
    assert "- [ ] **Pending step.**" in md
    assert "**Completed at:** 2026-04-26 15:00 UTC" in md


def test_groups_by_priority_in_required_recommended_optional_order() -> None:
    doc = _doc(
        suggestions=[
            Suggestion(id="a", action="Optional A", priority=PRIORITY_OPTIONAL),
            Suggestion(id="b", action="Recommended B", priority=PRIORITY_RECOMMENDED),
            Suggestion(id="c", action="Required C", priority=PRIORITY_REQUIRED),
        ],
    )
    md = render_markdown(doc)
    required_idx = md.index("Required C")
    recommended_idx = md.index("Recommended B")
    optional_idx = md.index("Optional A")
    assert required_idx < recommended_idx < optional_idx
    assert "## Required" in md
    assert "## Recommended" in md
    assert "## Optional" in md


def test_emits_dependencies_and_references_inline() -> None:
    doc = _doc(
        suggestions=[
            Suggestion(
                id="hash",
                action="Verify hash.",
                priority=PRIORITY_REQUIRED,
                expected_result="Match.",
                rationale="Integrity baseline.",
                references=["NIST SP 800-86 §5.2.2"],
            ),
            Suggestion(
                id="follow",
                action="Run AXIOM.",
                priority=PRIORITY_REQUIRED,
                depends_on=["hash"],
            ),
        ],
    )
    md = render_markdown(doc)
    assert "**Expected:** Match." in md
    assert "**Rationale:** Integrity baseline." in md
    assert "**References:** NIST SP 800-86 §5.2.2" in md
    assert "**Depends on:** `hash`" in md


def test_header_includes_case_name_and_reference_when_provided() -> None:
    handle = CaseHandle(
        name="Demo",
        case_reference="DM-1",
        examiner_name="Alex",
        scope=CaseScope(),
    )
    doc = _doc(suggestions=[Suggestion(id="a", action="A.")])
    md = render_markdown(doc, case=handle)
    assert "# CaseGuide Suggestions — Demo" in md
    assert "**Case reference:** DM-1" in md


def test_header_falls_back_to_generic_title_without_case() -> None:
    doc = _doc(suggestions=[Suggestion(id="a", action="A.")])
    md = render_markdown(doc)
    assert md.startswith("# CaseGuide Suggestions\n")
    # No "Case reference" line when there's no case handle.
    assert "Case reference" not in md


def test_multiline_action_is_collapsed_to_single_line() -> None:
    """GitHub task-list items break on hard newlines inside the body."""
    doc = _doc(
        suggestions=[
            Suggestion(
                id="x",
                action="First line.\n\nSecond line.\nThird line.",
                priority=PRIORITY_REQUIRED,
            ),
        ],
    )
    md = render_markdown(doc)
    # All three pieces collapse onto the headline line.
    assert "First line. Second line. Third line." in md


def test_skips_empty_priority_sections() -> None:
    doc = _doc(
        suggestions=[
            Suggestion(id="a", action="Only required.", priority=PRIORITY_REQUIRED),
        ],
    )
    md = render_markdown(doc)
    assert "## Required" in md
    assert "## Recommended" not in md
    assert "## Optional" not in md


def test_summary_line_reports_total_and_completed_counts() -> None:
    doc = _doc(
        suggestions=[
            Suggestion(id="a", action="A", completed=True),
            Suggestion(id="b", action="B"),
            Suggestion(id="c", action="C"),
        ],
    )
    md = render_markdown(doc)
    assert "3 suggestions" in md
    assert "1 completed" in md
