# Playbooks

JSON playbooks shipped with CaseGuide. The schema is documented in
`caseguide/playbooks.py` (the `Playbook` dataclass).

User overlays at `%LOCALAPPDATA%\CaseGuide\playbooks\*.json` replace
built-ins with the same `id`, so examiners can ship local refinements
without touching this directory.

Tool-variant ids in `tool_variants`:
- `axiom` — Magnet AXIOM
- `xways` — X-Ways Forensics
- `ftk` — AccessData FTK
- `autopsy` — Autopsy
- `cellebrite` — Cellebrite UFED

Match-criteria lists in `applies_to`:
- empty list = no constraint (matches anything)
- `["*"]` = explicit wildcard, same effect
- otherwise: case-insensitive substring across the scope's
  matching field
