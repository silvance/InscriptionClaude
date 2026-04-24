# Changelog

All notable changes to Inscription will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
