"""Render a :class:`SuggestionsDocument` as a markdown checklist.

The output is what an examiner would paste into a ticketing system,
the case file, the forensic notes, or a GitHub-style PR description.
GitHub-flavoured markdown's task-list syntax (``- [x]`` / ``- [ ]``)
is the lowest-common-denominator format that renders correctly in
GitHub, GitLab, Notion, Obsidian, and most modern markdown editors.

Two surfaces use this module:

- :meth:`SuggestionsPanel.copy_as_markdown` (clipboard) — quick
  paste flow when the examiner wants to drop the list into another
  tool right now.
- File → Export checklist as Markdown… — saves to disk with the same
  rendered text, useful for archival next to the case folder.

The renderer is pure functions and pure dataclasses; no Qt
dependencies, so the module is unit-testable without a display.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from caseguide.model import (
    PRIORITY_OPTIONAL,
    PRIORITY_RECOMMENDED,
    PRIORITY_REQUIRED,
)

if TYPE_CHECKING:
    from caseguide.case_reader import CaseHandle
    from caseguide.model import Suggestion, SuggestionsDocument

#: Order priorities are emitted in. Required first matches the panel's
#: own sort order so the markdown reads top-down the same way.
_PRIORITY_ORDER: tuple[str, ...] = (
    PRIORITY_REQUIRED,
    PRIORITY_RECOMMENDED,
    PRIORITY_OPTIONAL,
)

_SECTION_TITLES: dict[str, str] = {
    PRIORITY_REQUIRED: "Required",
    PRIORITY_RECOMMENDED: "Recommended",
    PRIORITY_OPTIONAL: "Optional",
}


def render_markdown(
    document: SuggestionsDocument, *, case: CaseHandle | None = None
) -> str:
    """Return a markdown checklist for ``document``.

    ``case`` is optional — when present, the title and a ``Case:``
    metadata line incorporate the case name and reference. Without it
    the rendered markdown is generic ("CaseGuide Suggestions") so the
    function still works for ad-hoc tests and clipboard flows where
    the case might not be open.
    """
    lines: list[str] = []
    lines.extend(_header_lines(document, case))
    for priority in _PRIORITY_ORDER:
        bucket = [s for s in document.suggestions if s.priority == priority]
        if not bucket:
            continue
        lines.append(f"## {_SECTION_TITLES[priority]}")
        lines.append("")
        for suggestion in bucket:
            lines.extend(_suggestion_lines(suggestion))
            lines.append("")
    leftover = [
        s for s in document.suggestions if s.priority not in _PRIORITY_ORDER
    ]
    if leftover:
        lines.append("## Other")
        lines.append("")
        for suggestion in leftover:
            lines.extend(_suggestion_lines(suggestion))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ----------------------------------------------------------- internals


def _header_lines(
    document: SuggestionsDocument, case: CaseHandle | None
) -> list[str]:
    title = "CaseGuide Suggestions"
    if case is not None and case.name:
        title = f"CaseGuide Suggestions — {case.name}"
    out: list[str] = [f"# {title}", ""]

    meta_bits: list[str] = []
    meta_bits.append(f"Generated {document.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    total = len(document.suggestions)
    completed = sum(1 for s in document.suggestions if s.completed)
    meta_bits.append(f"{total} suggestion{'s' if total != 1 else ''}")
    meta_bits.append(f"{completed} completed")
    out.append(" · ".join(meta_bits))
    out.append("")

    if case is not None and case.case_reference:
        out.append(f"**Case reference:** {case.case_reference}")
        out.append("")

    if document.scope_summary:
        out.append(f"**Scope:** {document.scope_summary}")
        out.append("")

    if document.playbooks:
        out.append("**Playbooks:** " + ", ".join(document.playbooks))
        out.append("")

    return out


def _suggestion_lines(suggestion: Suggestion) -> list[str]:
    """Render one suggestion as a checklist item plus indented detail lines."""
    box = "[x]" if suggestion.completed else "[ ]"
    headline = _escape_inline(suggestion.action) or "(no action)"
    category = (
        f" _(category: {_escape_inline(suggestion.category)})_"
        if suggestion.category
        else ""
    )
    out: list[str] = [f"- {box} **{headline}**{category}"]

    if suggestion.expected_result:
        out.append(f"  - **Expected:** {_escape_inline(suggestion.expected_result)}")
    if suggestion.rationale:
        out.append(f"  - **Rationale:** {_escape_inline(suggestion.rationale)}")
    if suggestion.depends_on:
        joined = ", ".join(f"`{d}`" for d in suggestion.depends_on)
        out.append(f"  - **Depends on:** {joined}")
    if suggestion.references:
        joined = "; ".join(_escape_inline(r) for r in suggestion.references)
        out.append(f"  - **References:** {joined}")
    if suggestion.completed and suggestion.completed_at is not None:
        stamp = suggestion.completed_at.strftime("%Y-%m-%d %H:%M UTC")
        out.append(f"  - **Completed at:** {stamp}")
    return out


def _escape_inline(text: str) -> str:
    """Strip newlines so markdown rendering doesn't break list nesting.

    GitHub and most editors render a hard newline inside a checklist
    item as "end of item", so we collapse multi-line strings to a
    single line. We don't escape ``*`` / ``_`` / ``` ` ``` characters
    — they're load-bearing in suggestion text (citations, code paths)
    and the markdown renderers handle them gracefully when the
    surrounding emphasis is balanced.
    """
    return " ".join(line.strip() for line in text.splitlines() if line.strip())
