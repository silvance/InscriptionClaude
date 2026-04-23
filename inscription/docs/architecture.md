# Inscription architecture

Inscription is a Scribe-style workflow capture studio for Windows. A user
records a workflow, the raw event stream is persisted unchanged, and a
separate step generator renders an editable draft guide from that stream.
Export formats target the guide layer; the raw layer stays verifiable.

## Two-layer output model

The central design decision is a strict separation between **what the tool
observed** and **what the guide says**.

- **Capture layer** — `raw_events`, `resolved_elements`, `screenshot_artifacts`
  tables. Every click, keypress milestone, window transition, and marker
  lands here verbatim. Screenshots carry a SHA-256 captured at persist
  time. Nothing in this layer is mutated after recording.
- **Guide layer** — `draft_steps` table. Generated from the raw layer by
  the step generator. Editable. Each step records the `source_event_ids`
  that produced it, plus a `manual_edit` flag that the regenerator honours.

The split makes it possible to show a reviewer exactly which step text came
from which raw event, and to rerun the generator without losing manual
cleanup.

## Layers

```
Presentation  ── inscription.ui
Coordination  ── inscription.ui.controller.SessionController
Step generation  ── inscription.steps
Capture        ── inscription.capture  (engine + sources + sink)
Resolution    ── inscription.resolve   (UIA + foreground fallbacks)
Platform      ── inscription.platform  (screen / hotkeys / foreground)
Storage       ── inscription.storage   (SessionRepository, SQLite, lockfile)
Export        ── inscription.export    (HTML today; MD/PDF/DOCX later)
Model         ── inscription.model     (pure dataclasses)
```

## Data model

```python
Session
├── SessionInfo        # name, started_at, ended_at, recorder_version
├── RawEvent[]         # timeline — sequence, kind, coords, key, screenshot ref
├── ResolvedElement[]  # UIA metadata per click with a confidence score
├── ScreenshotArtifact[]  # path + sha256 + dimensions
├── DraftStep[]        # generated guide rows — editable
└── ExportDocument[]   # generated guide files (HTML for alpha)
```

`EventKind` covers `click`, `double_click`, `key_press`, `text_input`
(reserved), `window_focus`, and `marker`.

## Event flow (recording)

```
Sources → engine queue → worker thread → enrichment → sink
   │                                         │
   │                                         ├─ screenshot (for clicks,
   │                                         │   window-focus, markers)
   │                                         ├─ foreground inspect (every event)
   │                                         └─ UIA element lookup (clicks only)
   ▼
ClickSource, KeyboardMilestoneSource,
WindowFocusSource, MarkerSource
```

Sources listen on pynput / polling threads. They only build
`RawCaptureEvent` objects and call `engine.submit()` — no I/O, no
resolution. The engine worker thread does the heavy work (screenshot,
UIA, foreground read) so source listeners stay responsive.

Platform objects (`ScreenCapturer`, `ForegroundInspector`,
`ElementResolver`) are built **inside** the worker thread via factories:
`mss` and UIA aren't thread-safe and must be owned by the thread that
uses them.

## Step generation

`StepGenerator.regenerate()` produces draft steps from the raw event
stream. Three reduction passes:

1. **Window-focus noise.** A `window_focus` event followed within 0.6 s by
   a click is assumed to be a side-effect of that click (the click caused
   the focus change) and is dropped.
2. **Click dedup.** Two clicks on the same resolved element within 0.8 s
   collapse into one step. Screenshot association prefers the first.
3. **Text rendering.** Confidence-scaled wording:
   - UIA resolved (confidence ≥ 0.6): `Click the 'Save' Button in Notepad.`
   - Foreground fallback (0.3): `Click in the Notepad window.`
   - No resolution: `Click the mouse.`

Manual edits are preserved: if a step's `source_event_ids` match a
previously-edited step, the edited text wins and `manual_edit=True`
carries forward.

## Element resolution

```
create_element_resolver(inspector)
  │
  ├─ Windows + pywinauto present → UiaElementResolver
  │      │
  │      └─ on miss → ForegroundFallbackResolver
  │
  └─ else → ForegroundFallbackResolver
```

`UiaElementResolver` queries the UIA tree at `(x, y)`. `ForegroundFallbackResolver`
returns a low-confidence element derived from the active window. `NullResolver`
is available for tests and unusual environments.

## Persistence

One session = one directory under `%LOCALAPPDATA%\Inscription\workspace\`.

```
<slug>/
├── session.db           SQLite with the tables listed above
├── manifest.json        summary (name, counts, timestamps) for the picker
├── screenshots/         PNGs referenced by raw_events / draft_steps
├── exports/             generated guides and staged assets
└── .inscription/
    └── session.lock     PID-based; stale locks from crashed processes are
                         reclaimed on open
```

Manifest writes are atomic (staged `.tmp` + rename). The DB connection is
opened with `check_same_thread=False` and serialised through a
per-repository lock so the capture worker and the Qt main thread can share
the connection safely.

## Testing approach

- `test_storage` exercises create/reopen/lock/round-trip on the SQLite
  layer without any Qt.
- `test_capture` runs the full engine with fake screen/foreground/resolver
  implementations — no pynput, no mss, deterministic.
- `test_steps` seeds the DB directly and runs `StepGenerator`.
- `test_export` renders an HTML file and checks it's self-contained.
- `test_integration` ties capture → generate → export together.
- `test_main_window` smoke-tests the Qt main window with pytest-qt's
  offscreen platform.

## Near-term direction

- **Beta:** Markdown + DOCX exporters, merge-adjacent-steps UX, better
  UIA coverage for Electron/web surfaces, richer screenshot annotation
  (arrows, redactions).
- **1.0:** Inno Setup installer, signing, crash reporting, sample library.
- **Evidence mode (future):** an opt-in toggle that disables click dedup
  and window-focus coalescing, enforces `manual_edit` provenance, and
  signs the raw layer.
