@echo off
REM ============================================================
REM   Build the air-gapped Inscription Suite USB bundle.
REM
REM   Double-click this file. It will:
REM     1. Set up the Python venv if needed (one-time)
REM     2. Verify Ollama is installed (link if not)
REM     3. Pop a folder picker for the USB drive
REM     4. Pull models, build apps, write the bundle
REM     5. Show a "done" message with the path
REM
REM   No need to remember -Destination flags or activate
REM   anything by hand. Re-run any time the source code or
REM   models change to refresh the bundle.
REM ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Build-Bundle.ps1" %*
