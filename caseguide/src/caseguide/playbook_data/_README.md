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

`applies_to.keywords` is an optional short-circuit OR: any keyword
substring found in the joined scope text fires the playbook
regardless of the structured fields. Reserve it for steps that
should surface even on under-specified scopes (image-hash, RAM
acquisition) — tool-specific steps should leave it empty so they
don't leak into cases that haven't picked the tool.

The descriptive fields (`exam_types`, `device_classes`,
`evidence_items`) match softly: an empty scope value is treated
as inconclusive and passes the rule. Only `primary_tools` is
strict — an unset tool fails any tool-specific rule, so AXIOM /
X-Ways / Cellebrite playbooks don't appear for cases that
haven't picked them.
