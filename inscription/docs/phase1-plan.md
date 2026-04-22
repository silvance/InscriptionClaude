# Phase 1 — Capture Core MVP

**Status:** Planning → in progress
**Depends on:** Phase 0 (project scaffolding) complete
**Expected duration:** 3-4 weeks of focused part-time work

---

## Goal

By the end of Phase 1, an examiner can:

1. Launch Inscription and create a new case with a validated case number
2. Open an existing case from the case list
3. Press `Ctrl+Shift+S` anywhere on the system to capture the current screen
4. See the captured screenshot appear in a step list with a timestamp
5. Add a short title and note body to the step
6. Close the application and reopen the case to find all steps preserved

That's it. No review UI polish, no export, no forensic-tool adapters, no buffer, no HUD. Those come later.

## Non-goals for Phase 1

Explicit to avoid scope creep:

- Review/editing UI beyond the bare minimum needed to see that capture works
- Screenshot annotation tools (arrows, boxes, redaction) — Phase 2
- Export to .docx — Phase 2
- Forensic context providers — Phase 3
- Always-on rolling buffer — Phase 4 (but architecture accommodates it)
- HUD overlay widget — Phase 4
- Panic-pause hotkey — Phase 4 (not meaningful until buffering exists)
- Case archival to NAS on close — Phase 2 (simpler to tackle with export)
- Per-examiner preferences beyond what already exists in `Config`
- Multi-monitor capture (Phase 1 captures primary monitor; multi-monitor in Phase 4)

## Architecture overview

Phase 1 introduces five new subsystems. Each is behind an interface so the OS-specific implementations can be swapped:

```
┌──────────────────────────────────────────────────────────────────┐
│                         Main UI (Qt)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐        │
│  │ Case List    │  │ New Case     │  │ Case Workspace   │        │
│  │ Dialog       │  │ Dialog       │  │ (step list view) │        │
│  └──────────────┘  └──────────────┘  └─────────┬────────┘        │
└─────────────────────────────────────────────────┼────────────────┘
                                                  │
                            ┌─────────────────────┴─────────────┐
                            │      CaseController (Qt-aware)    │
                            │  open/close/create cases          │
                            │  wire UI ↔ capture ↔ repository   │
                            └───┬───────────────┬───────────┬───┘
                                │               │           │
                  ┌─────────────┴──┐  ┌─────────┴──────┐  ┌─┴──────────┐
                  │ CaseRepository │  │ CaptureEngine  │  │ Hotkey     │
                  │  (SQLite +     │  │ (producer/     │  │ Manager    │
                  │   filesystem)  │  │  consumer)     │  │ (pynput)   │
                  └────────┬───────┘  └───────┬────────┘  └────────────┘
                           │                  │
                           │         ┌────────┴────────┐
                           │         │ ScreenCapturer  │
                           │         │   (mss impl)    │
                           │         └─────────────────┘
                           │
                  ┌────────┴─────────┐
                  │  Case on disk    │
                  │  ~/workspace/    │
                  │  <case-slug>/    │
                  │    case.db       │
                  │    screenshots/  │
                  │    manifest.json │
                  └──────────────────┘
```

## Key design decisions

### Case storage: local-first, flush-on-save

Cases live in `workspace_root/<case-slug>/` during active editing. A case on the
NAS is just a zipped archive of this directory. Opening a case from the NAS
unzips it into the workspace; closing/saving re-archives and flushes back.

**Why:** SQLite over SMB is a known corruption risk. Local-first also means
editing works when the NAS is unreachable (e.g. someone hasn't entered credentials
in this session yet), which is a real Inscription use case.

For Phase 1 we implement only the local workspace side. NAS round-trip lands in
Phase 2 alongside export.

### Case directory layout

```
workspace/HSV-2026-0317/
├── case.db              SQLite database (primary truth)
├── manifest.json        quick-inspect metadata (case number, examiner, counts)
├── screenshots/         raw PNG captures
│   ├── 2026-04-22T14-32-05-0001.png
│   └── 2026-04-22T14-37-11-0002.png
└── .inscription/        internal state, schema version, lock file
    ├── version
    └── case.lock
```

The `.inscription/` subdirectory keeps our bookkeeping separate from the
examiner's content. `manifest.json` enables fast case-list population without
opening every DB.

### SQLite schema (Phase 1 subset)

Only the tables we need this phase. Full schema is in the design doc; we add
tables incrementally as phases need them.

```sql
-- Case metadata. One row per database.
CREATE TABLE case_info (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    case_number     TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    examiner        TEXT    NOT NULL,
    agency          TEXT,
    description     TEXT,
    created_at      TEXT    NOT NULL,  -- ISO 8601 UTC
    updated_at      TEXT    NOT NULL,
    schema_version  INTEGER NOT NULL
);

-- Capture sessions. Phase 1 auto-creates one per case-open.
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    ended_at        TEXT,
    capture_mode    TEXT    NOT NULL DEFAULT 'hotkey'
);

-- Individual steps. The core event table.
CREATE TABLE steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sequence        INTEGER NOT NULL,
    captured_at     TEXT    NOT NULL,
    kind            TEXT    NOT NULL,  -- 'hotkey_capture' | 'manual_note'
    title           TEXT    NOT NULL DEFAULT '',
    body_markdown   TEXT    NOT NULL DEFAULT '',
    screenshot_path TEXT              -- relative to case root
);

CREATE INDEX idx_steps_session_sequence ON steps(session_id, sequence);
```

Schema version lives in `case_info.schema_version` and in `.inscription/version`.
Migrations are handled by a small in-repo migration runner (no Alembic; the
schema is simple enough that Alembic is overkill, and we avoid a dependency).

### Capture engine: producer/consumer from day one

Even though Phase 1 only wires up the hotkey path, the capture engine is
structured as:

```
┌───────────────┐    capture request    ┌───────────────┐
│ Source        │ ───────────────────► │ CaptureEngine │
│ (hotkey,      │                      │ (orchestrator)│
│  timer,       │                      └──────┬────────┘
│  manual)      │                             │
└───────────────┘                             ▼
                                       ┌───────────────┐
                                       │ ScreenCapturer│
                                       │   (grabs PNG) │
                                       └──────┬────────┘
                                              │
                              ┌───────────────┼────────────────┐
                              ▼               ▼                ▼
                         ┌─────────┐  ┌──────────────┐  ┌────────────┐
                         │  Sink:  │  │  Sink:       │  │  Sink:     │
                         │  case   │  │  buffer      │  │  future…   │
                         │  repo   │  │ (Phase 4)    │  │            │
                         └─────────┘  └──────────────┘  └────────────┘
```

Each source publishes a `CaptureRequest`. The engine fans out captures to
registered sinks. Phase 1 has one source (hotkey) and one sink (case
repository). Phase 4 adds a timer source and a buffer sink without changing
the engine's contract.

### Platform abstraction

Three interfaces live in `inscription.platform`:

- `ScreenCapturer` — `capture(monitor: int | None) -> CapturedImage`
- `HotkeyManager` — register/unregister global hotkeys
- `ForegroundInspector` — stub for now; returns `(window_title, process_name)`. Phase 3 providers use this.

Each has an `mss`/`pynput`/`pywinauto`-backed Windows implementation and a
development stub that works on Kali (captures whatever X11 monitor is active,
simulates hotkeys via a debug menu). Phase 1 ships both. Phase 5 (or whenever
Windows-only features land) may drop the dev stubs to binaries.

### Threading model

Qt main thread owns all UI. The capture engine runs in a dedicated
`QThread`. Hotkey events arrive on `pynput`'s listener thread and are
marshalled via Qt signals. Disk I/O (saving PNG, writing to SQLite) happens
on the capture engine thread, not the UI thread — this is important for
latency budget (hotkey-to-thumbnail < 200ms).

## Task breakdown

Each task is sized to be committable as a single PR. Order matters where
dependencies exist; parallel where noted.

### Milestone 1 — Data model and repository (week 1)

- **T1.1** Create `inscription.cases` package with `Case`, `Step`, `Session` dataclasses
- **T1.2** Create `inscription.storage` package with `CaseRepository` (SQLite-backed)
- **T1.3** Migration runner (start at schema v1; test forward-only migrations)
- **T1.4** Create-case logic: slug generation, directory layout, DB init, manifest write
- **T1.5** Open/close-case logic with lockfile to prevent double-open
- **T1.6** Repository unit tests (tmp_path-based, pure Python, Kali-compatible)
- **T1.7** Case-number validator using `Config.case_number_regex`

### Milestone 2 — Platform abstraction (week 1-2, parallel with M1)

- **T2.1** `inscription.platform` package with abstract interfaces
- **T2.2** `MssScreenCapturer` Windows/Linux implementation (real)
- **T2.3** `PynputHotkeyManager` implementation
- **T2.4** `StubForegroundInspector` returning window title + PID (Phase 3 will replace with real UIA on Windows)
- **T2.5** Platform interface tests with mocks

### Milestone 3 — Capture engine (week 2)

- **T3.1** `CaptureEngine` class with source/sink registration
- **T3.2** `HotkeySource` wraps `HotkeyManager`, emits `CaptureRequest`
- **T3.3** `CaseRepositorySink` persists captures to active case
- **T3.4** Engine runs in its own `QThread`; Qt signal/slot marshalling
- **T3.5** Latency benchmarking test (not a CI gate, just a local script)

### Milestone 4 — UI (week 3)

- **T4.1** `CaseListDialog` — case picker on app start (lists cases in workspace)
- **T4.2** `NewCaseDialog` — form with validation, creates on OK
- **T4.3** Replace placeholder central widget with `CaseWorkspaceWidget` (stub step list)
- **T4.4** `StepListWidget` — Qt `QListView` with custom item delegate showing thumbnail + title + timestamp
- **T4.5** `StepDetailPanel` — side panel showing selected step, editable title/body
- **T4.6** Wire `CaseController` to connect UI, capture, repo

### Milestone 5 — Integration and polish (week 4)

- **T5.1** End-to-end test: programmatically create case, fire capture, verify DB+file state
- **T5.2** Crash recovery: what happens when Inscription dies mid-capture
- **T5.3** Manual test pass on Windows 11 VM
- **T5.4** Update `CHANGELOG.md` and `README.md`
- **T5.5** Tag v0.2.0

## Testing strategy

**Unit tests** cover `cases`, `storage`, and `platform` packages. Target 80%+
coverage on non-UI code. These run on Kali without a display.

**Qt tests** use `pytest-qt` with `QT_QPA_PLATFORM=offscreen`. They cover widget
construction, signal emission, and controller logic. These also run on Kali.

**Integration tests** drive the full stack headlessly: create-case-in-tmp-path,
inject a fake capture request via the engine, verify DB and filesystem state.
Run in CI.

**Manual tests on Windows 11 VM** happen at end of each milestone. Milestone 5
includes a written test script the examiner (you) follows on a clean VM to
validate. Record screenshots for the brief.

**Performance budgets for Phase 1:**

- Hotkey press → screenshot saved → step row visible: < 250ms
- Case open (100 steps): < 500ms
- Case create: < 200ms
- App startup to case picker: < 2s on a cold VM

## Risks and mitigations

**`pynput` hotkey conflicts in Windows VMs.** If the VM is capturing input
(Hyper-V enhanced session, VMware unity), global hotkeys may behave differently
than bare-metal. Mitigation: test on VM early in the phase; have a fallback
path to in-app hotkeys (only work when Inscription is focused).

**`mss` DPI scaling on Windows.** Per-monitor DPI on Windows 11 can produce
surprising screenshot dimensions. Mitigation: test against a high-DPI monitor
config, add a Qt `QScreen.grabWindow()` fallback behind a setting.

**SQLite locking when Inscription opens a case that's "still open" from a
previous crashed session.** Mitigation: lockfile with PID; on startup, if the
lockfile PID is dead, reclaim the lock. Add a "force-open" option for the
pathological case.

**Scope creep from "just one more thing."** Mitigation: this document. Every
new feature gets evaluated against the explicit non-goals list. If it's listed
there, it waits for its phase.

## Deliverables

End of Phase 1 ships:

- `inscription` package with `cases`, `storage`, `platform`, `capture`, `ui` subpackages fully populated
- Functional case create/open/close
- Working hotkey-triggered screenshot capture
- Persistent step list
- Test suite with 80%+ coverage on non-UI code
- Updated docs (`CHANGELOG.md`, `README.md`, this Phase 1 plan marked complete)
- Tagged release v0.2.0 with a built Windows zip attached
- A short manual-test script you run on a VM to validate before briefing anyone

## What Phase 2 will tackle next

- Proper review UI (step reordering, merging, deletion)
- Screenshot annotation tools
- Export to .docx via Jinja2 template
- Case close/archive workflow (zip to NAS)
- Template system

---

## Next action

Proceed to Milestone 1 → Task T1.1 (dataclasses for `Case`, `Step`, `Session`).
