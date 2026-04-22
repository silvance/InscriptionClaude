# Documentation

This directory holds Inscription's design and user-facing documentation.

## Files expected here

- `design.md` — canonical design document. Drop the design doc generated during
  the planning phase (`forensic-notes-design.md`) in here and rename it to
  `design.md` so it travels with the repository.
- `user-guide.md` — lands in Phase 5.
- `adapter-authoring.md` — lands with Phase 3 (forensic tool adapters).

## Conventions

- Markdown only. No generated HTML, no Sphinx for now — keep it readable in a
  GitHub web view and inside Obsidian.
- Diagrams live alongside the doc that uses them, ideally as Mermaid fenced
  code blocks so they render on GitHub without a build step.
- Update `CHANGELOG.md` when user-visible behaviour changes; design-only edits
  do not need a changelog entry.
