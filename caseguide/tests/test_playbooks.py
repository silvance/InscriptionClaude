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
    """The shipped JSON files all parse cleanly."""
    playbooks = load_playbooks(user_dir=__import__("pathlib").Path("/nonexistent"))
    ids = {p.id for p in playbooks}
    expected = {
        # Universal / cross-tool foundations.
        "verify-image-hash",
        "chain-of-custody-intake",
        "memory-image-acquisition",
        # AXIOM track.
        "axiom-ci-processing",
        "axiom-timeline-analysis",
        # X-Ways track.
        "xways-rvs-processing",
        # Autopsy track.
        "autopsy-ci-processing",
        # Cellebrite (mobile) track.
        "cellebrite-mobile-extraction",
        "cellebrite-mobile-analysis",
        # Topical: Windows MRU + CSAM.
        "mru-folder-access",
        "csam-hash-set-verification",
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


def test_soft_field_passes_when_scope_is_blank() -> None:
    """A descriptive rule should not punish under-specified scopes."""
    pb = Playbook(
        id="image",
        title="Image",
        action="Verify hash.",
        applies_to=AppliesTo(evidence_items=["E01", "image"]),
    )
    matcher = PlaybookMatcher([pb])
    # Empty scope.evidence_items used to fail — now it's inconclusive,
    # so the playbook still fires. The examiner can complete or remove
    # if it doesn't apply.
    assert matcher.match(CaseScope(exam_type="anything")) == [pb]


def test_strict_primary_tool_rule_still_requires_explicit_match() -> None:
    """primary_tools stays strict so AXIOM steps don't leak."""
    pb = Playbook(
        id="axiom",
        title="AXIOM",
        action="Process.",
        applies_to=AppliesTo(primary_tools=["axiom"]),
    )
    matcher = PlaybookMatcher([pb])
    # Scope without a primary_tool must NOT trigger an AXIOM-only step.
    assert matcher.match(CaseScope(exam_type="CI")) == []
    assert matcher.match(CaseScope(primary_tool="axiom")) == [pb]
    assert matcher.match(CaseScope(primary_tool="xways")) == []


def test_keyword_present_in_scope_text_short_circuits_match() -> None:
    """Any keyword in the joined scope text fires the playbook."""
    pb = Playbook(
        id="hash",
        title="Hash",
        action="Verify.",
        # Other rules are restrictive; keywords are the escape hatch.
        applies_to=AppliesTo(
            evidence_items=["E01"],
            keywords=["acquisition", "image"],
        ),
    )
    matcher = PlaybookMatcher([pb])
    # Even with no evidence_items, the exam_type string contains
    # "image" so the keyword hit fires the playbook.
    assert matcher.match(CaseScope(exam_type="Forensic image acquisition")) == [pb]


def test_keyword_does_not_override_strict_tool_when_no_match() -> None:
    """Keywords short-circuit, but only matter to the playbook itself."""
    pb = Playbook(
        id="axiom-keyword",
        title="AXIOM",
        action="Process.",
        applies_to=AppliesTo(
            primary_tools=["axiom"],
            keywords=["timeline"],
        ),
    )
    matcher = PlaybookMatcher([pb])
    # Keyword present in scope text → playbook fires regardless of
    # primary_tools, because keywords are an OR short-circuit.
    assert matcher.match(CaseScope(exam_type="timeline analysis")) == [pb]


def test_cellebrite_mobile_case_fires_mobile_chain_not_disk_chain() -> None:
    """A Cellebrite UFED case shouldn't surface AXIOM / X-Ways disk steps."""
    matcher = PlaybookMatcher(
        load_playbooks(user_dir=__import__("pathlib").Path("/nonexistent"))
    )
    scope = CaseScope(
        exam_type="CSAM",
        primary_tool="cellebrite",
        device_classes=["mobile", "ios"],
        evidence_items=["UFDR extraction"],
    )
    matched_ids = {p.id for p in matcher.match(scope)}
    assert "cellebrite-mobile-extraction" in matched_ids
    assert "cellebrite-mobile-analysis" in matched_ids
    assert "axiom-ci-processing" not in matched_ids
    assert "xways-rvs-processing" not in matched_ids
    assert "autopsy-ci-processing" not in matched_ids


def test_csam_case_with_image_fires_hash_set_verification() -> None:
    """A CSAM disk case should pull in the hash-set verification step."""
    matcher = PlaybookMatcher(
        load_playbooks(user_dir=__import__("pathlib").Path("/nonexistent"))
    )
    scope = CaseScope(
        exam_type="CSAM possession",
        primary_tool="axiom",
        evidence_items=["E01 image"],
    )
    matched_ids = {p.id for p in matcher.match(scope)}
    assert "verify-image-hash" in matched_ids
    assert "csam-hash-set-verification" in matched_ids


def test_incident_response_case_fires_memory_acquisition() -> None:
    """An IR case picks up the live RAM acquisition step regardless of tool."""
    matcher = PlaybookMatcher(
        load_playbooks(user_dir=__import__("pathlib").Path("/nonexistent"))
    )
    # No primary_tool — memory acquisition is universal.
    scope = CaseScope(exam_type="incident response")
    matched_ids = {p.id for p in matcher.match(scope)}
    assert "memory-image-acquisition" in matched_ids


def test_under_specified_image_acquisition_case_now_fires_image_hash() -> None:
    """Regression for the user's reported scenario.

    A case with only ``exam_type='Forensic image acquisition'`` and
    everything else empty used to match only ``chain-of-custody-intake``.
    With the matcher rework, ``verify-image-hash`` fires too — via the
    keyword path — since hashing is a required step for any acquired
    image regardless of other scope details.
    """
    matcher = PlaybookMatcher(
        load_playbooks(user_dir=__import__("pathlib").Path("/nonexistent"))
    )
    scope = CaseScope(exam_type="Forensic image acquisition")
    matched_ids = {p.id for p in matcher.match(scope)}
    assert "chain-of-custody-intake" in matched_ids
    assert "verify-image-hash" in matched_ids
    # AXIOM / X-Ways tool-specific steps must not leak into a case
    # that hasn't picked a tool.
    assert "axiom-ci-processing" not in matched_ids
    assert "xways-rvs-processing" not in matched_ids
