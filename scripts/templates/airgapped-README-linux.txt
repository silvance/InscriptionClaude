Inscription suite -- air-gapped bundle (Linux)
==============================================

This folder is a self-contained install of three forensic tools plus
the local LLM runtime they use. It runs entirely offline; no internet
connection is needed at any point after copying the folder onto this
machine.

Contents
--------

  Inscription/        Capture a workflow, generate a step guide.
                      Note: UIA capture is Windows-only; on Linux this
                      ships in degraded form -- case management, step
                      rewriting, and exports work, but automated step
                      capture does not.
  CaseForge/          Case intake, chain-of-custody, report generation.
  CaseGuide/          LLM-assisted exam coach (next-action suggestions).
  ollama/             Local LLM runtime (Ollama).
  models/             Pre-staged model weights and manifests.
  install.sh          One-shot installer (verifies integrity, copies the
                      bundle, creates a .desktop launcher entry).
  start-suite.sh      Daily launcher (the .desktop entry runs this).
  version.json        Build provenance: git SHA, build timestamp, bundled
                      model list. Useful for "which build is this?" later.
  manifest.json       SHA-256 of every file. install.sh reads this and
                      verifies the bundle before installing -- a bad USB
                      transfer fails loudly instead of producing a silently
                      corrupt install.

To start
--------

  First time on this workstation:
    From a terminal inside this folder:
        ./install.sh
    The installer copies the bundle to
        ~/.local/share/InscriptionSuite/
    and creates a .desktop entry under
        ~/.local/share/applications/inscription-suite.desktop
    Look for "Inscription Suite" in your applications menu after that.

  Daily use after that:
    Applications menu -> Inscription Suite, or run from a terminal:
        ~/.local/share/InscriptionSuite/start-suite.sh

  Quick test before installing (optional):
    ./start-suite.sh
    Runs the launcher straight from this folder without copying
    anything onto the workstation. Useful when you just want to verify
    the bundle is intact.

The launcher will:
  1. Point Ollama at the ./models directory inside this folder.
  2. Start a local Ollama server on 127.0.0.1:11435 (a dedicated port,
     so it never collides with a system-wide Ollama install).
  3. Wait until the server reports ready.
  4. If more than one model is bundled, ask which one the apps should
     use this session.
  5. Show a small picker -- pick the app you want to open.

Closing the picker stops the bundled Ollama server. Re-run
start-suite.sh any time to bring it back up; the model question is
asked again so you can switch without rebooting.

Models bundled
--------------

  gemma4:latest    Shared default for both Inscription's AI rewrite step
                   and CaseGuide's suggestion refinement (~10 GB).
  granite4:tiny-h  Smaller fallback (~4 GB) for workstations that can't
                   keep gemma4 resident in memory.

Both are cached under ./models. The launcher asks which to use; the
apps read the choice from the SUITE_LLM_MODEL env var. You can still
override per app from Settings -- the Model field is an editable
dropdown populated from whatever Ollama lists.

Troubleshooting
---------------

  "Bundled Ollama did not become ready within 60s"
      Another Ollama server may already be holding the dedicated port
      11435 from a previous run. Find and kill it:
          pgrep -laf 'ollama serve'
          kill <pid>
      Then re-run start-suite.sh.

  "Permission denied" on start-suite.sh or install.sh
      Make sure the executable bits are set:
          chmod +x install.sh start-suite.sh
      Some USB filesystems (FAT32 / exFAT) drop +x on copy.

  "ollama: error while loading shared libraries"
      The bundle's runner libraries weren't found. Make sure you're
      running start-suite.sh (which sets LD_LIBRARY_PATH) rather than
      invoking ollama/bin/ollama directly.

  An app fails to launch
      Try running the binary directly from inside the matching folder
      (e.g. ./Inscription/Inscription). If that works but the launcher
      doesn't, the issue is with the launcher's environment; capture
      its stderr (./start-suite.sh 2>&1 | tee /tmp/start-suite.log)
      and open a support ticket with the log.
