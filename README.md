# Inscription

Offline forensic examination notes and step-logging tool for Windows.

**Status:** Phase 0 — scaffolding only. Not yet functional for case work.

---

## What this is

Inscription is a desktop tool for digital forensic examiners that streamlines
note-taking and step-logging during an examination. It captures screenshots,
structured steps, free-form notes, and forensic-tool context (AXIOM, X-Ways,
Cellebrite Physical Analyzer) and produces a polished editable notes document
for attachment to the final forensic report.

Unlike online alternatives, Inscription runs fully offline and is designed for
air-gapped examination workstations.

See `docs/design.md` for the full design document and phased development plan.

## Requirements

- Windows 10 or 11 (x64) as the deployment target
- Python 3.12 for development

## Development setup

```powershell
git clone <repo-url>
cd inscription

python -m venv .venv
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Run from source
python -m inscription

# Run the full local check (lint + types + tests)
.\scripts\dev.ps1 all

# Individual steps
.\scripts\dev.ps1 lint
.\scripts\dev.ps1 typecheck
.\scripts\dev.ps1 test
```

## Building a distributable

```powershell
.\scripts\dev.ps1 build
# or equivalently:
pyinstaller packaging/inscription.spec --noconfirm
```

Output lands in `dist/Inscription/`. Copy the whole folder to the target
workstation and run `Inscription.exe`. Phase 5 will replace this with a proper
Inno Setup installer.

## Project layout

```
inscription/
├── src/inscription/          application package
│   ├── __main__.py           `python -m inscription` entry point
│   ├── app.py                QApplication bootstrap
│   ├── config.py             typed QSettings wrapper
│   ├── paths.py              filesystem path resolution
│   ├── logging_setup.py      rotating-file logging
│   └── ui/                   Qt widgets
├── tests/                    pytest suite
├── packaging/                PyInstaller spec (Inno Setup later)
├── scripts/                  dev helpers
├── docs/                     design and user documentation
└── .github/workflows/        CI
```

## Runtime filesystem layout

All local data lives under `%LOCALAPPDATA%\Inscription\`:

| Path              | Purpose                                              |
|-------------------|------------------------------------------------------|
| `config.ini`      | User preferences (QSettings, INI format)             |
| `logs/`           | Rotating log files (5 MiB × 10)                      |
| `workspace/`      | Local cache of the currently open case               |
| `cache/`          | Thumbnails, buffered captures awaiting promotion     |

Active and archived cases live on the NAS; `workspace/` is a performance cache
that gets flushed back on save/close.

## License

TBD — pending decision on distribution scope.
