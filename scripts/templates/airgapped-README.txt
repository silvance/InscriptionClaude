Inscription suite — air-gapped bundle
=====================================

This folder is a self-contained install of three forensic tools plus the
local LLM runtime they use. It runs entirely offline; no internet
connection is needed at any point after copying the folder onto this
machine.

Contents
--------

  Inscription\        Capture a Windows workflow, generate a step guide.
  CaseForge\          Case intake, chain-of-custody, report generation.
  CaseGuide\          LLM-assisted exam coach (next-action suggestions).
  ollama\             Local LLM runtime (Ollama).
  models\             Pre-staged model weights and manifests.
  start-suite.ps1     First-run launcher (this is what you double-click).

To start
--------

  Right-click  start-suite.ps1  and pick  "Run with PowerShell".

The launcher will:
  1. Point Ollama at the .\models directory inside this folder.
  2. Start a local Ollama server on 127.0.0.1:11434.
  3. Wait until the server reports ready.
  4. Show a small picker — pick the app you want to open.

Closing the picker stops the bundled Ollama server. Re-run start-suite.ps1
any time to bring it back up.

Models bundled
--------------

  granite4.0:8b   Inscription's default for the AI rewrite step.
  gemma4:latest   CaseGuide's default for suggestion refinement.

Both are cached under .\models. The apps are pre-configured to talk to
http://localhost:11434 — no further setup needed.

Troubleshooting
---------------

  "Ollama did not become ready within 60s"
      Another Ollama install on this machine may already be holding the
      port. Stop that one (Task Manager -> ollama.exe -> End task) and
      re-run start-suite.ps1.

  "Cannot run scripts because running scripts is disabled"
      Open PowerShell as Administrator on this machine and run:
          Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
      Then re-run start-suite.ps1.

  An app fails to launch
      Try running the .exe directly from inside the matching folder
      (e.g. .\Inscription\Inscription.exe). If that works but the
      launcher doesn't, the issue is with the launcher's environment;
      open a support ticket with the message text.
