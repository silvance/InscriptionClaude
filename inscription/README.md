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

### CLI flags

```
python -m inscription --case-dir <path>
```

`--case-dir <path>` makes Inscription store this run's sessions inside
`<path>` instead of the default `%LOCALAPPDATA%\Inscription\workspace\`.
Intended for the upcoming **CaseForge** integration: CaseForge creates
the case directory, then launches Inscription pointed at it. The flag
does not modify the saved config — it's per-run only. The case folder
name appears in the title bar.

## Core workflow

1. Launch Inscription.
2. File → Open Session, start a new session with a name.
3. Press **● Record**, carry out the workflow on your desktop.
4. Press **■ Stop**. Draft steps are auto-generated from the captured events.
5. *(optional)* File → Rewrite with AI… — hands the session to a local LLM
   for a more natural rewrite. See [Local LLM setup](#local-llm-setup).
6. Click a step to edit its text; remove steps that shouldn't appear in the
   guide.
7. File → Export as HTML or Markdown.

## Local LLM setup

The rule-based step generator always runs; the LLM rewrite is opt-in. Any
OpenAI-compatible chat-completions endpoint works.

**Fastest path — [Ollama](https://ollama.com):**

```powershell
# Install Ollama, then pull a model.
ollama pull granite4.0:8b     # or llama3.1:8b, qwen2.5:7b-instruct, etc.
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

## Deployment topologies

Forensic exam workflows often involve a host workstation plus one or
more analysis VMs. Inscription is designed to run wherever the work is
happening — install it on the box that owns the keyboard and mouse for
the workflow you want to capture.

### 1. Bare metal (recommended for demos and host-side work)

Install Inscription on the workstation directly. UIA element resolution,
screenshots, and hotkeys all work as designed against any application
on that machine. No extra setup.

### 2. Inside a VM (recommended for live exam work)

When the actual examination happens inside a Windows VM (analysis
sandbox, mounted-image host, isolated network), install Inscription
**inside the VM**. UIA can only see controls in the OS it's running in,
so this is the only way to get full-fidelity step text for actions
performed against tools running in the VM.

Two operational tips that pay for themselves on the first case:

- **Put the case directory on a shared folder** between host and VM
  (VirtualBox shared folders / VMware HGFS / Hyper-V Enhanced Session
  redirect). Launch with
  `python -m inscription --case-dir "Z:\Cases\HSV-2026-0317"` (or
  whatever the shared mount is). Notes, screenshots, and the forensic
  PDF land on the host filesystem in real time, survive VM reverts,
  and the report builder running on the host can read from the same
  path.
- **Local LLM placement**: install Ollama / LM Studio inside the VM
  for the simplest setup, *or* run it on the host and point the VM's
  `llm.base_url` at the host's IP if your VM has host-only networking.
  The latter avoids a second model download but requires you to open
  the LLM port to the VM.

### 3. Inscription on host while you work in a VM (not recommended)

This works mechanically — the host's mouse and keyboard listeners fire
when you click into the VM viewer window, and screenshots include the
VM's display pixels — but step text quality drops noticeably because
UIA can't see inside the guest. Actions read as
*"Click in the VirtualBox window"* instead of
*"Click the 'Save' button"*. Acceptable as a stopgap, not a recommended
mode.

A future enhancement could ship a thin in-VM agent that streams
events back to a host-side Inscription, getting the best of both
worlds. The integration contract for that is reserved but unbuilt;
see `docs/integration.md`.

## License

TBD — pending decision on distribution scope.
