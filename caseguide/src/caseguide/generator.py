"""Suggestion generator: turn matched playbooks into a SuggestionsDocument.

This is the v0.1 generator — purely deterministic. Given a case scope:

1. Match every playbook whose ``applies_to`` overlaps the scope.
2. Render each match as a :class:`caseguide.model.Suggestion`, using
   the playbook's ``tool_variants[primary_tool]`` action wording when
   one is defined.

Commit 5 adds an LLM augmentation pass after this — the same matched
playbooks, plus the scope summary, get sent to the model so it can
prune duplicates, add scope-specific suggestions, and tighten wording.
For now the deterministic output stands on its own and gives the UI
something useful to render.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from caseguide import __version__
from caseguide.model import Suggestion, SuggestionsDocument, utcnow

if TYPE_CHECKING:
    from caseguide.case_reader import CaseScope
    from caseguide.playbooks import Playbook, PlaybookMatcher


def generate_suggestions(
    *,
    scope: CaseScope,
    matcher: PlaybookMatcher,
) -> SuggestionsDocument:
    """Build the suggestions feed deterministically from matched playbooks."""
    matched = matcher.match(scope)
    suggestions = [_playbook_to_suggestion(p, scope) for p in matched]
    return SuggestionsDocument(
        generated_at=utcnow(),
        scope_summary=_scope_summary(scope),
        playbooks=[p.id for p in matched],
        suggestions=suggestions,
        caseguide_version=__version__,
    )


def _playbook_to_suggestion(playbook: Playbook, scope: CaseScope) -> Suggestion:
    return Suggestion(
        id=playbook.id,
        action=playbook.rendered_action(scope.primary_tool),
        category=playbook.category,
        priority=playbook.priority,
        expected_result=playbook.expected_result,
        rationale=playbook.rationale,
        references=list(playbook.references),
        depends_on=list(playbook.depends_on),
    )


def _scope_summary(scope: CaseScope) -> str:
    """Short human-readable summary used in the suggestions header."""
    bits: list[str] = []
    if scope.exam_type:
        bits.append(scope.exam_type)
    if scope.primary_tool:
        bits.append(f"tool: {scope.primary_tool}")
    if scope.device_classes:
        bits.append("devices: " + ", ".join(scope.device_classes))
    if not bits and scope.summary:
        return scope.summary.strip().splitlines()[0][:200]
    return " · ".join(bits) if bits else "(scope unspecified)"
