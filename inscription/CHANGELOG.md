# Changelog

All notable changes to Inscription will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — Phase 1 capture MVP

### Added

- Domain model package (`inscription.cases`) with `Case`, `CaseInfo`, `Session`,
  `Step`, `StepKind`, and `CaseManifest` dataclasses plus filesystem-safe slug
  generation.
- Persistence layer (`inscription.storage`) with `CaseRepository`, SQLite schema
  and forward-only migration runner, JSON manifest with atomic writes, PID-based
  lockfile with stale-lock reclamation, and a `list_cases` helper.
- Thread-safe repository: SQLite opened with `check_same_thread=False` plus a
  per-repository lock, so the capture engine worker thread and the Qt main
  thread can share a connection safely.
- Platform abstraction (`inscription.platform`) with `ScreenCapturer`
  (`mss`-backed with a null fallback), `HotkeyManager` (`pynput`-backed with a
  stub for headless dev), and `ForegroundInspector` (ctypes-based Win32 on
  Windows, placeholder on Linux).
- Capture engine (`inscription.capture`) with a producer/consumer architecture:
  worker thread, bounded queue, `CaptureSource`/`CaptureSink` contracts
  (`CaptureSink` is a `typing.Protocol` so Qt widgets can duck-type it without
  metaclass fights), `HotkeySource`, and `CaseRepositorySink`.
- UI layer (`inscription.ui`): `CaseListDialog`, `NewCaseDialog` with regex
  validation against `Config.case_number_regex`, `CaseWorkspaceWidget`,
  `StepListWidget` with thumbnails, `StepDetailPanel` with debounced saves,
  `QtCaptureBridge` for cross-thread signal marshalling, and `CaseController`
  orchestrating the whole lifecycle.
- Bash dev helper (`scripts/dev.sh`) mirroring the existing PowerShell one.
- 60 tests covering slug generation, repository create/open/reopen/locking,
  manifest I/O, platform abstractions, capture engine producer/consumer flow,
  hotkey source wiring, repository sink persistence, main window construction,
  and end-to-end integration (create → capture → close → reopen → verify).

### Fixed

- Embedded placeholder PNG bytes corrected (previous hex decoded to invalid
  PNG); regenerated via `zlib`+`struct` and verified round-trip through PIL.
- Lockfile collision detection: any live PID holding a lock — including the
  current process — now counts as a collision, so two `CaseRepository`
  instances within one process can't both open the same case.
- `pynput` import defensive on headless Linux (it tries to open an X
  connection at import time); we now fall back to the stub hotkey manager
  when import fails rather than crashing at startup.

## [0.1.0] — Phase 0 scaffolding

### Added

- Project scaffolding with src-layout and Hatchling build backend.
- PySide6-based empty main window with menu bar, status bar, and About dialog.
- Typed configuration wrapper around `QSettings` (INI format at
  `%LOCALAPPDATA%\Inscription\config.ini`).
- `paths` module resolving application directories under `%LOCALAPPDATA%`.
- Rotating-file logging (never transmits, local disk only, 5 MiB × 10).
- GitHub Actions CI: ruff lint + format check, mypy strict, pytest with
  coverage, packaged-exe build artifact on main.
- PyInstaller spec for one-folder Windows build.
- Unit tests for paths, config, and version; smoke tests for main window.
- PowerShell dev helper script (`scripts/dev.ps1`).
