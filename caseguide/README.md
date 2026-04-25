# CaseGuide

LLM-assisted exam coach for the Inscription forensic-exam suite.

**Status:** 0.1 alpha — skeleton bootstrap. Playbook library, UI, and
LLM augmentation land in follow-up commits.

---

## Where it sits in the suite

| Tool         | Role |
|--------------|------|
| **CaseForge** | Builds the case folder, captures examiner identity / case reference / exam scope. |
| **CaseGuide** *(this)* | Reads the scope, selects matching procedural playbooks, asks the LLM to tailor them to the specific case, and writes a checklist of suggested actions Inscription surfaces while the examiner records. |
| **Inscription** | Records the actual desktop work into editable, exportable forensic notes. |
| **Tool 3** *(planned)* | Pulls evidentiary-marked notes + admin metadata + the suggestions checklist into the final report. |

CaseGuide reads `<case-root>/case.json` (CaseForge's artefact) for
scope, picks matching playbooks, runs an LLM augmentation pass, and
writes `<case-root>/.caseguide/suggestions.json`. Inscription is
read-only on `.caseguide/`. The contract lives in
`inscription/docs/integration.md`.

## Tool-aware playbooks

Most exam steps are tool-agnostic at the level of intent ("verify the
SHA-256", "extract registry hives") but dramatically tool-specific in
how they're performed. CaseGuide playbooks carry one canonical body
per logical step plus a `tool_variants` dict that overrides the action
wording for AXIOM, X-Ways, FTK, etc. The case's `primary_tool` (set
in CaseForge's Scope tab) decides which variant renders.

## Requirements

- Windows 10 or 11 (x64) as the deployment target
- Python 3.12 for development
- A local OpenAI-compatible LLM endpoint (Ollama / LM Studio / llama.cpp --server)

## Development setup

```powershell
git clone <repo-url>
cd caseguide

python -m venv .venv
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Run from source
python -m caseguide

# Open a case directly
python -m caseguide --case-dir "C:\Cases\HSV-2026-0317"

# Full local check (lint + types + tests)
.\scripts\dev.ps1 all
```

## Layout on disk

Per-user state lives under `%LOCALAPPDATA%\CaseGuide\`:

| Path             | Purpose |
|------------------|---------|
| `config.ini`     | User preferences (LLM endpoint, etc.) |
| `logs/`          | Rotating log files |
| `playbooks/`     | Optional user-authored playbook overlays (drop JSON files here to extend the built-in set) |

Built-in playbooks ship inside the package at
`src/caseguide/playbook_data/`.

The case-side artefact CaseGuide writes lives **inside the case
directory CaseForge built**, not under CaseGuide's own data root:

```
<case-root>/.caseguide/suggestions.json
```

## Build a distributable

```powershell
.\scripts\dev.ps1 build
# or:
pyinstaller packaging/caseguide.spec --noconfirm
```

Output lands in `dist/CaseGuide/`.

## License

TBD — pending decision on distribution scope.
