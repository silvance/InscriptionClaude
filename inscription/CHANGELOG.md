# Changelog

All notable changes to Inscription will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Editor upgrades.** Three new affordances on the step list:
  - **Drag-to-reorder.** Move steps with the mouse; sequence numbers
    persist via ``SessionRepository.reorder_steps``.
  - **Merge with next step.** Right-click a step → "Merge with next
    step" combines its ``source_event_ids`` with the following step,
    deletes the second row, marks the result ``manual_edit``.
  - **Split off first event.** Right-click a step that covers more
    than one source event → "Split off first event" peels the first
    event into its own step and keeps the rest in a sibling row
    inserted directly after.
- ``SessionRepository.merge_steps`` and ``split_step`` back the new
  context-menu actions; both mark touched rows as ``manual_edit`` so
  later AI/regenerate passes preserve them verbatim.

### Added

- **Scroll capture.** New ``ScrollSource`` (``pynput.on_scroll``)
  records mouse-wheel scrolling. Continuous scrolling is debounced —
  a flick produces one ``EventKind.SCROLL`` event with the cumulative
  amount encoded as ``"down 8"`` / ``"up 3, right 2"``. No screenshot
  (scrolling is fluid; a frozen mid-scroll frame isn't useful), but
  the engine still attaches foreground info so the rendered step
  reads *"Scroll down 8 in Google Chrome."*. Closes the gap that was
  causing the LLM to fabricate "navigated through tabs" when the user
  was just scrolling.

### Changed

- **LLM system prompt is stricter** about not inventing actions that
  aren't in the input timeline. Specifically forbids fabricating
  scrolling, tab switching, or navigation when no events back them up.

### Added

- **Rewrite with AI.** File → Rewrite with AI… hands the session's raw
  events + UIA metadata to a local LLM (or any OpenAI-compatible server)
  and replaces the rule-based draft steps with the model's rewritten
  version. Merges related events into single imperative sentences where
  the rule-based generator is forced to emit one step per click.
- ``inscription.llm`` package: ``LLMClient`` (stdlib-only ``urllib``
  POST against a chat-completions endpoint), ``build_user_prompt`` /
  ``parse_response`` (tolerates markdown code fences, drops steps whose
  ``source_event_ids`` don't match any real event so the guide layer's
  provenance stays clean), ``StepRewriter`` (preserves manual edits,
  picks each merged step's screenshot from its last source event).
- Config keys ``llm.enabled``, ``llm.base_url`` (defaults to
  ``http://localhost:11434/v1`` — Ollama), ``llm.model`` (defaults to
  ``granite3.3:8b``), ``llm.timeout_s``, ``llm.api_key``.
- Modal progress dialog + QThread worker so the rewrite runs off the
  UI thread; any failure (connection, timeout, malformed response)
  leaves the existing draft intact and shows the error to the user.

### Added

- **Crop-and-highlight screenshots** in the HTML export. Each step's
  image is a tight crop around the clicked UIA element with a red click
  ring drawn at the press point instead of a full-screen PNG. Makes
  multi-step guides dramatically more readable on-screen and in print.
- ``ResolvedElement.bounding_rect`` stores the UIA
  ``BoundingRectangle`` reported at resolve time; schema bumped to v2
  with an ALTER TABLE migration that leaves v1 sessions working.
- New module ``inscription.render`` with ``crop_highlight`` — a pure
  Pillow function that crops a PNG around an element rect, pads it,
  clamps to image bounds, and draws a translucent click marker. Keeps
  the export path Qt-free.
- ``Pillow>=10`` dependency.

### Changed

- ``WindowFocusSource`` now keys "did the window change?" on the native
  window handle (``hwnd``) rather than the window title. Typing in
  Notepad updates the title once per keystroke
  (``*h - Notepad`` → ``*he - Notepad`` → …), and the old keying treated
  each title update as a new window switch. ``ForegroundInfo`` gains an
  ``hwnd`` field; non-Windows inspectors leave it ``None`` and the source
  falls back to title + process name.

### Fixed

- Taskbar / Start-menu / Alt-Tab clicks no longer render misleading step
  text. Previously UIA would correctly name the shell element (e.g.
  *'Python 3.14 - 1 running window' Button*), but step text would glue it
  onto whatever foreground app was still behind it —
  *"Click the 'Python 3.14 - 1 running window' Button in World of Warcraft."*
  ``ResolvedElement`` now carries ``owner_process_name`` (populated from
  UIA's ``process_id``); when it differs from the foreground process, the
  step text drops the ``in <window>`` suffix. Schema bumped 2 → 3 with an
  ALTER TABLE migration.
- Window-focus screenshots now grab the monitor the newly-focused
  window is actually on. Previously the source fell through to
  ``ScreenCapturer.capture()`` (no args), which always returned
  ``mss.monitors[1]`` — on many Windows multi-monitor setups that's the
  wrong display, producing a guide where every "Switch to …" step
  showed a screen the user wasn't actually working on. ``ForegroundInfo``
  now carries ``window_rect`` (from Win32 ``GetWindowRect``), and
  ``WindowFocusSource`` feeds the rect's center to ``capture_at`` to
  pick the right monitor.
- ``SessionSink`` no longer crashes with
  ``sqlite3.IntegrityError: UNIQUE constraint failed: screenshot_artifacts.relative_path``
  when a user stops and restarts recording on the same open session.
  Screenshot filenames are now derived from the event's ``processed_at``
  timestamp (microsecond precision); the engine's single-threaded worker
  plus the cost of ``mss.grab`` guarantees uniqueness without a seeded
  counter.
- Click screenshots now capture the monitor under the click point instead
  of always capturing the primary monitor. ``ScreenCapturer.capture_at(x, y)``
  walks ``list_monitors`` and picks the monitor whose bbox contains the
  point; ``ClickSource`` calls it with the pynput coordinates.
- ``pywinauto`` is now declared as a Windows-only dependency so the UIA
  resolver actually loads on the target platform. Previously the install
  silently skipped it and every click fell back to "Click in the X window"
  text.
- ``mss`` shutdown no longer emits a spurious ``ReleaseDC`` warning on
  Windows; the known-harmless exception is logged at DEBUG.

### Changed

- **Screenshots are now captured on the source's own thread** rather than
  on the engine worker. Clicks carry the *pre-click* frame (the UI the
  user was looking at when they pressed the button) instead of a frame
  read several queue hops later. ``ClickSource`` and ``WindowFocusSource``
  each own a dedicated ``ScreenCapturer`` (``mss`` is not thread-safe, so
  per-thread instances are required).
- ``CaptureEngine`` no longer takes a ``screen_factory``; it does
  foreground + UIA resolution + SHA-256 of the attached bytes, and
  nothing else. ``RawCaptureEvent`` gains ``png_bytes`` / ``png_width`` /
  ``png_height`` and loses ``want_screenshot``.
- Global hotkeys moved from ``MarkerSource`` into ``SessionController``:
  **Ctrl+Shift+R** toggles recording so the user can start/stop without
  clicking Inscription's own window (and capturing it), and
  **Ctrl+Shift+M** drops a marker. Recording-toggle is active whenever
  a session is open; the marker hotkey is active only while recording.

### Removed

- ``MarkerSource`` class (folded into the controller).
- ``EngineStats`` counters (never surfaced anywhere).
- ``EventKind.TEXT_INPUT`` and its render path (never emitted by any
  source; we don't capture typed text).
- ``ForegroundInfo.extras`` (unused).
- ``SessionRepository.transaction()`` (unused).
- ``_resolver_factory`` indirection in the controller — ``create_element_resolver``
  already has the right signature.

## [0.3.0] — Scribe-style pivot (alpha)

### Changed

- **Product pivot.** Inscription is now a Scribe-style workflow capture studio
  that auto-generates editable step-by-step guides, not a forensic
  examination notes tool. The underlying raw-capture layer (timestamps,
  coordinates, UIA metadata, screenshot hashes, recorder version) is still
  preserved separately from the editable draft-step layer, so a future
  "evidence mode" toggle could reintroduce stricter-than-alpha behavior
  without schema changes.
- Domain objects replaced: `Case`, `CaseInfo`, `Session`, `Step` →
  `Session`, `SessionInfo`, `RawEvent`, `ResolvedElement`,
  `ScreenshotArtifact`, `DraftStep`, `ExportDocument`. Single module
  `inscription.model`.
- Storage layer rewritten: `session.db` with tables `session_info`,
  `raw_events`, `resolved_elements`, `screenshot_artifacts`,
  `draft_steps`. New `SessionRepository`. PID-based lockfile is unchanged.
- Capture engine rewritten to enrich raw events with screenshot +
  foreground + optional UIA resolution, then fan out to sinks. Platform
  objects are now instantiated inside the worker thread via factories
  because `mss` and UIA aren't thread-safe.
- `Config` dropped the forensic-only `case_number_regex` and `nas_root`
  keys. Only `workspace_root`, `theme`, and window geometry remain.

### Added

- `inscription.capture.click_source` — `pynput` mouse listener with
  double-click detection.
- `inscription.capture.keyboard_source` — milestone-key listener (Enter,
  Tab, Esc, backspace, delete, F1–F12). Ordinary characters are not
  captured; privacy and noise are both the reason.
- `inscription.capture.window_source` — foreground-window poll (250 ms)
  that emits events only on real transitions.
- `inscription.capture.marker_source` — user-triggered marker bound to
  Ctrl+Shift+M and the toolbar button.
- `inscription.resolve` — `ElementResolver` abstraction with
  `UiaElementResolver` (Windows + pywinauto), `ForegroundFallbackResolver`,
  and `NullResolver`. Confidence is graded 0.0–0.9.
- `inscription.steps` — `StepGenerator` that collapses clicks on the same
  element within an 0.8 s window, drops window-focus events that are
  caused by the next click, and renders draft step text that scales with
  resolver confidence. Manual edits are preserved across regeneration when
  the source event set is unchanged.
- `inscription.export.html` — self-contained HTML guide written under
  `<session>/exports/` with screenshots staged into `exports/assets/`.
- `ScreenshotArtifact.sha256` recorded at capture time for provenance.
- `SessionInfo.recorder_version` stamped on session creation.
- UI: `RecorderBar` with Record/Stop + Marker + live event counter;
  `StepListWidget` with thumbnails; `StepEditorPanel` with debounced
  persistence and a remove/restore toggle; `SessionListDialog` +
  `NewSessionDialog`; `SessionWorkspaceWidget`; `SessionController`
  orchestrating the whole lifecycle.

### Removed

- `inscription.cases` package, `CaseRepository`, case number regex
  validation, NAS workspace concept.
- `inscription.capture.hotkey_source`, `inscription.capture.repository_sink`
  (superseded by new sources and `SessionSink`).

## [0.2.0] — Phase 1 capture MVP

### Added

- Domain model package (`inscription.cases`) with `Case`, `CaseInfo`,
  `Session`, `Step`, `StepKind`, and `CaseManifest` dataclasses plus
  filesystem-safe slug generation.
- Persistence layer (`inscription.storage`) with `CaseRepository`, SQLite
  schema and forward-only migration runner, JSON manifest with atomic
  writes, PID-based lockfile with stale-lock reclamation.
- Platform abstraction (`inscription.platform`) with `ScreenCapturer`,
  `HotkeyManager`, and `ForegroundInspector`.
- Capture engine (`inscription.capture`) with producer/consumer architecture,
  `CaptureSource`/`CaptureSink` contracts, `HotkeySource`, and
  `CaseRepositorySink`.
- UI layer (`inscription.ui`) with case list + new case dialogs, step list
  with thumbnails, step detail with debounced saves, Qt bridge for
  cross-thread signals, and case controller.

## [0.1.0] — Phase 0 scaffolding

### Added

- Project scaffolding with src-layout and Hatchling build backend.
- PySide6-based empty main window with menu bar, status bar, About dialog.
- Typed configuration wrapper around `QSettings`.
- `paths` module resolving application directories.
- Rotating-file logging.
- GitHub Actions CI: ruff lint + format check, mypy strict, pytest with
  coverage, packaged-exe build artifact on main.
- PyInstaller spec for one-folder Windows build.
- Dev helpers (`scripts/dev.ps1`).
