# Inscription

Record a Windows workflow, auto-generate a step-by-step guide with screenshots,
review and edit, then export.

**Status:** 0.3 alpha — capture → step generation → HTML export on a single
thread of plumbing. Usable end-to-end, rough around the edges.

---

## What it does

Inscription is a desktop capture studio in the shape of Scribe, not Steps
Recorder. You press **Record**, do whatever workflow you want to document, and
press **Stop**. Inscription captures:

- Mouse clicks (with UI Automation element metadata where available)
- Active window changes
- Keyboard milestones — `Enter`, `Tab`, `Esc`, function keys
- Screenshots taken on each click and window transition

The raw stream is preserved exactly as observed. A separate step generator
groups those events into a short, readable procedure with one screenshot per
step. Manual edits to the text are kept across regenerations; the raw capture
layer is never mutated.

Export as HTML today; Markdown/PDF/DOCX later.

## Design principles

- Clarity over cleverness.
- Capture first, clean up second.
- The generated guide is a draft, not final truth. The raw layer is.
- Windows-native look; cross-platform dev is a nice-to-have, not a target.

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

# Full local check (lint + types + tests)
.\scripts\dev.ps1 all
```

## Core workflow

1. Launch Inscription.
2. File → Open Session, start a new session with a name.
3. Press **● Record**, carry out the workflow on your desktop.
4. Press **■ Stop**. Draft steps are auto-generated from the captured events.
5. *(optional)* File → Rewrite with AI… — hands the session to a local LLM
   for a more natural rewrite. See [Local LLM setup](#local-llm-setup).
6. Click a step to edit its text; remove steps that shouldn't appear in the
   guide.
7. File → Export as HTML.

## Local LLM setup

The rule-based step generator always runs; the LLM rewrite is opt-in. Any
OpenAI-compatible chat-completions endpoint works.

**Fastest path — [Ollama](https://ollama.com):**

```powershell
# Install Ollama, then pull a model.
ollama pull granite3.3:8b     # or gemma2:9b, llama3.1:8b, etc.
```

Ollama exposes `http://localhost:11434/v1` automatically; that's the
default Inscription points at. To change model or endpoint, edit
`%LOCALAPPDATA%\Inscription\config.ini`:

```ini
[llm]
base_url=http://localhost:11434/v1
model=granite3.3:8b
timeout_s=180
```

Inscription also works with LM Studio's local server and
`llama.cpp --server`, and with remote providers when you set
`llm.api_key` — point `llm.base_url` at whatever OpenAI-compatible
endpoint you have.

## Architecture

```
  Sources          Capture engine              Sinks
  ───────          ──────────────              ─────
 ┌──────────┐     ┌───────────────────┐       ┌──────────────┐
 │ Click    │───► │  Queue → worker   │─────► │ SessionSink  │───► SQLite + PNG
 │ Key      │───► │  + screenshot     │       │ (raw layer)  │
 │ Window   │───► │  + UIA resolve    │       └──────────────┘
 │ Marker   │───► │  + foreground     │       ┌──────────────┐
 └──────────┘     └───────────────────┘─────► │ QtBridge     │───► UI updates
                                              └──────────────┘

  Step generator (post-capture)
  ─────────────────────────────
  raw_events ──► group / dedup ──► render ──► draft_steps (editable)

  HTML exporter
  ─────────────
  draft_steps + screenshots ──► self-contained HTML in exports/
```

## Layout on disk

All local data lives under `%LOCALAPPDATA%\Inscription\`:

| Path              | Purpose                                              |
|-------------------|------------------------------------------------------|
| `config.ini`      | User preferences (QSettings INI)                     |
| `logs/`           | Rotating log files (5 MiB × 10)                      |
| `workspace/`      | Root for all session folders                         |
| `cache/`          | Reserved for thumbnails / buffered captures          |

Each session is its own folder:

```
workspace/<slug>/
├── session.db              SQLite: events, elements, screenshots, steps
├── manifest.json           summary for the session picker
├── screenshots/            PNG files referenced by events
├── exports/                generated HTML (+ staged assets)
└── .inscription/           internal metadata and the lockfile
```

## Package layout

```
inscription/
├── src/inscription/
│   ├── app.py                 QApplication bootstrap
│   ├── __main__.py            python -m inscription entrypoint
│   ├── model.py               Session / RawEvent / DraftStep / ...
│   ├── config.py              typed QSettings wrapper
│   ├── paths.py               filesystem path resolution
│   ├── logging_setup.py       rotating-file logging
│   ├── platform/              screen, hotkeys, foreground window
│   ├── resolve/               UIA element lookup + fallbacks
│   ├── capture/               engine + click/keyboard/window/marker sources
│   ├── steps/                 event-grouping and step text generator
│   ├── export/                HTML exporter (alpha)
│   └── ui/                    Qt widgets + controller
├── tests/                     pytest suite
├── packaging/                 PyInstaller spec
├── scripts/                   dev helpers (PowerShell + Bash)
└── docs/                      design notes
```

## Build a distributable

```powershell
.\scripts\dev.ps1 build
# or:
pyinstaller packaging/inscription.spec --noconfirm
```

Output lands in `dist/Inscription/`. Copy that folder to the target machine
and run `Inscription.exe`. An Inno Setup installer is planned for beta.

## License

TBD — pending decision on distribution scope.
