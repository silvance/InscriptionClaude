# Changelog

All notable changes to Inscription will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
