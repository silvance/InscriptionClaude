# Documentation

Inscription's design and user-facing documentation.

## Files in this directory

- `architecture.md` — canonical architecture reference (layers, data model,
  event flow).
- `integration.md` — the contract Inscription exposes to the planned
  three-tool suite (CaseForge → Inscription → report builder): session
  folder layout, SQLite schema, the `evidentiary` flag, and the
  forward-only-migration stability promise.
- `phase1-plan.md` — historical record of the earlier forensic-focused Phase
  1. Kept for provenance; superseded by the Scribe-style pivot in 0.3.
- `user-guide.md` — planned for beta.

## Conventions

- Markdown only. No generated HTML, no Sphinx — keep docs readable in a
  GitHub web view.
- Diagrams live alongside the doc that uses them, ideally as Mermaid fenced
  code blocks so they render on GitHub without a build step.
- Update `CHANGELOG.md` when user-visible behaviour changes; design-only
  edits do not need a changelog entry.
