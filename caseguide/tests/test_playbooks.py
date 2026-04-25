"""Playbook loader + PlaybookMatcher behaviour."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from caseguide.case_reader import CaseScope
from caseguide.playbooks import (
    AppliesTo,
    Playbook,
    PlaybookMatcher,
    ToolVariant,
    load_playbooks,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write(directory: Path, name: str, payload: dict[str, object]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_builtin_playbooks_load_and_parse() -> None:
    """The five shipped JSON files all parse cleanly."""
    playbooks = load_playbooks(user_dir=__import__("pathlib").Path("/nonexistent"))
    ids = {p.id for p in playbooks}
    expected = {
        "verify-image-hash",
        "chain-of-custody-intake",
        "axiom-ci-processing",
        "axiom-timeline-analysis",
        "xways-rvs-processing",
        "mru-folder-access",
    }
    assert expected.issubset(ids)


def test_user_playbook_overlay_replaces_builtin(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    _write(
        overlay,
        "verify-image-hash",
        {
            "id": "verify-image-hash",
            "title": "Site-specific hash verification",
            "action": "Run our internal hash-checker harness instead.",
        },
    )
    playbooks = load_playbooks(user_dir=overlay)
    by_id = {p.id: p for p in playbooks}
    assert by_id["verify-image-hash"].title == "Site-specific hash verification"


def test_malformed_playbook_is_skipped(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    (overlay / "broken.json").write_text("{not valid", encoding="utf-8")
    _write(
        overlay,
        "good",
        {"id": "good", "title": "Good", "action": "Do the thing."},
    )
    playbooks = load_playbooks(user_dir=overlay)
    assert any(p.id == "good" for p in playbooks)
    assert not any(p.id == "broken" for p in playbooks)


def test_playbook_without_action_is_dropped(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    _write(overlay, "no-action", {"id": "no-action", "title": "Empty"})
    playbooks = load_playbooks(user_dir=overlay)
    assert all(p.id != "no-action" for p in playbooks)


def test_rendered_action_uses_tool_variant() -> None:
    pb = Playbook(
        id="x",
        title="X",
        action="Generic action.",
        tool_variants={"axiom": ToolVariant(action="AXIOM-specific action.")},
    )
    assert pb.rendered_action("axiom") == "AXIOM-specific action."
    assert pb.rendered_action("xways") == "Generic action."
    assert pb.rendered_action("") == "Generic action."


def test_matcher_picks_universal_playbooks() -> None:
    """A playbook with empty applies_to fits any scope."""
    pb = Playbook(id="universal", title="Universal", action="Always.")
    matcher = PlaybookMatcher([pb])
    matched = matcher.match(CaseScope(exam_type="CSAM"))
    assert matched == [pb]


def test_matcher_filters_on_primary_tool() -> None:
    axiom_only = Playbook(
        id="axiom",
        title="AXIOM",
        action="AXIOM only.",
        applies_to=AppliesTo(primary_tools=["axiom"]),
    )
    xways_only = Playbook(
        id="xways",
        title="X-Ways",
        action="X-Ways only.",
        applies_to=AppliesTo(primary_tools=["xways"]),
    )
    matcher = PlaybookMatcher([axiom_only, xways_only])
    matched = matcher.match(CaseScope(primary_tool="axiom"))
    assert [p.id for p in matched] == ["axiom"]


def test_matcher_substring_match_is_case_insensitive() -> None:
    pb = Playbook(
        id="ci",
        title="CI",
        action="Run.",
        applies_to=AppliesTo(exam_types=["CI"]),
    )
    matcher = PlaybookMatcher([pb])
    # Exact, lowercase, and substring all match.
    assert matcher.match(CaseScope(exam_type="CI")) == [pb]
    assert matcher.match(CaseScope(exam_type="ci")) == [pb]
    assert matcher.match(CaseScope(exam_type="ci-investigation")) == [pb]


def test_matcher_priority_order_is_required_first() -> None:
    required = Playbook(id="r", title="R", action=".", priority="required")
    recommended = Playbook(id="rec", title="Rec", action=".", priority="recommended")
    optional = Playbook(id="o", title="O", action=".", priority="optional")
    matcher = PlaybookMatcher([recommended, optional, required])
    ordered = matcher.match(CaseScope())
    assert [p.id for p in ordered] == ["r", "rec", "o"]


def test_wildcard_in_rule_matches_anything() -> None:
    pb = Playbook(
        id="wild",
        title="Wild",
        action="Anywhere.",
        applies_to=AppliesTo(exam_types=["*"], primary_tools=["axiom"]),
    )
    matcher = PlaybookMatcher([pb])
    # Any exam_type matches; primary_tool must still be axiom.
    assert matcher.match(CaseScope(exam_type="CSAM", primary_tool="axiom")) == [pb]
    assert matcher.match(CaseScope(exam_type="anything", primary_tool="axiom")) == [pb]
    assert matcher.match(CaseScope(exam_type="anything", primary_tool="xways")) == []


def test_starter_playbook_axiom_ci_matches_axiom_ci_case() -> None:
    """End-to-end: built-in axiom-ci-processing fires for an AXIOM CI case."""
    matcher = PlaybookMatcher(
        load_playbooks(user_dir=__import__("pathlib").Path("/nonexistent"))
    )
    scope = CaseScope(
        exam_type="CI investigation",
        primary_tool="axiom",
        evidence_items=["E01 image"],
    )
    matched_ids = {p.id for p in matcher.match(scope)}
    assert "axiom-ci-processing" in matched_ids
    assert "verify-image-hash" in matched_ids
    assert "chain-of-custody-intake" in matched_ids
    # The X-Ways playbook must not fire for an AXIOM case.
    assert "xways-rvs-processing" not in matched_ids
