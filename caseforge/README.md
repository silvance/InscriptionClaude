# CaseForge

Case intake and scope tool for the Inscription forensic-exam suite.

**Status:** 0.1 alpha — create cases, edit scope, launch Inscription.

---

## Where it sits in the suite

| Tool         | Role |
|--------------|------|
| **CaseForge** *(this)* | Builds the case folder, captures examiner identity / case reference / exam scope. |
| **CaseGuide** *(planned)* | Reads the scope and emits a best-practice action checklist Inscription surfaces during the exam. |
| **Inscription** | Records the actual desktop work into editable, exportable forensic notes. |
| **Tool 3** *(planned)* | Pulls evidentiary-marked notes from Inscription + admin metadata from CaseForge into the final report. |

CaseForge writes one file per case: `case.json` inside the case
directory. Inscription reads that directory via `--case-dir`; the
report builder reads `case.json` for the report header. The contract
lives in `inscription/docs/integration.md`.

## What v0.1 does

- **New case wizard** — case name, case reference, examiner identity,
  structured scope block. Writes `case.json` into a fresh slugified
  directory under your workspace.
- **Case browser** — lists cases under the workspace plus any you've
  opened explicitly from elsewhere; click to open.
- **Case editor** — three-tab view (Case / Examiner / Scope) for
  editing metadata after intake.
- **Launch Inscription** — primary button; spawns
  `inscription --case-dir <path>` using a configured executable, your
  PATH, or `python -m inscription` as a final fall-back.
- **Settings** — examiner-identity defaults that auto-fill new cases,
  workspace root, Inscription executable path.

Deferred for later: case archival, multi-examiner ACLs, encryption at
rest, anything network.

## Requirements

- Windows 10 or 11 (x64) as the deployment target
- Python 3.12 for development

## Development setup

```powershell
git clone <repo-url>
cd caseforge

python -m venv .venv
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Run from source
python -m caseforge

# Full local check (lint + types + tests)
.\scripts\dev.ps1 all
```

## Layout on disk

Per-user state lives under `%LOCALAPPDATA%\CaseForge\`:

| Path             | Purpose |
|------------------|---------|
| `config.ini`     | User preferences (QSettings INI) |
| `logs/`          | Rotating log files (5 MiB × 10) |
| `workspace/`     | Default root for case directories |
| `cache/`         | Reserved |

Each case is its own folder:

```
workspace/<case-slug>/
└── case.json          everything CaseForge writes
```

Inscription will add its own `<session-slug>/` folders inside the
same case directory when you launch it from CaseForge — see
`inscription/docs/integration.md` for the full layout.

## Build a distributable

```powershell
.\scripts\dev.ps1 build
# or:
pyinstaller packaging/caseforge.spec --noconfirm
```

Output lands in `dist/CaseForge/`. Copy that folder to the target
machine and run `CaseForge.exe`.

## License

TBD — pending decision on distribution scope.
