# Air-gapped deployment

This page is for the operator who **builds** the air-gapped bundle on a
connected Windows machine and then **carries** it to the offline
workstation. The bundle is fully self-contained: three apps, the Ollama
runtime, and the pre-pulled model weights.

For day-to-day developer setup, see `SETUP.md` instead.

---

## What gets shipped

```
InscriptionSuite-Airgapped\
├── Inscription\          ~150 MB    capture + step generation
├── CaseForge\            ~150 MB    case intake + reporting
├── CaseGuide\            ~150 MB    LLM coach
├── ollama\               ~150 MB    bundled Ollama Windows runtime
├── models\               ~14 GB     two model snapshots
│   ├── blobs\            (sha256-* weight files)
│   └── manifests\        (one per model:tag pulled)
├── install.ps1                      one-shot installer (run on first
│                                    setup -- copies the bundle to a
│                                    permanent location and creates a
│                                    Start Menu shortcut)
├── start-suite.ps1                  daily launcher (called by the
│                                    Start Menu shortcut after install,
│                                    asks which model to use this session)
├── version.json                     build provenance (git SHA, build
│                                    timestamp, bundled model list)
├── manifest.json                    SHA-256 of every file in the
│                                    bundle -- install.ps1 verifies
│                                    this before copying onto the
│                                    workstation
└── README.txt                       operator notes
```

Total: **~15 GB**. Use a 32 GB USB drive or larger.

---

## Build-machine prerequisites

A Windows 10/11 box with internet access during the build only.

1. Clone this repo and follow `SETUP.md` to get the venv working with
   all four packages installed editable.
2. Install Ollama for Windows from <https://ollama.com/download/windows>.
3. From any PowerShell window:
   ```powershell
   ollama pull gemma4:latest
   ollama pull granite4:tiny-h
   ```
   `gemma4:latest` is the shared default both Inscription and CaseGuide
   point at (~10 GB). `granite4:tiny-h` ships as a smaller (~4 GB)
   fallback the operator can switch to via `start-suite.ps1` on
   workstations that can't fit gemma4 in memory.

---

## Building the bundle

### One-shot wrapper (recommended)

`scripts\prepare-bundle.ps1` pulls the chosen models, runs `package-airgapped.ps1`, optionally fetches the latest PowerShell 7 MSI alongside it, and (with `-Destination`) copies the finished bundle to an external drive in one go. Typical use from the repo root with the venv activated:

```powershell
.venv\Scripts\Activate.ps1
.\scripts\prepare-bundle.ps1 -Destination E:\
```

That stages everything into `E:\InscriptionSuite-Airgapped\` ready to carry. Useful flags:

```powershell
# Add the 70B fallback for the operator who's willing to wait on heavier rewrites.
.\scripts\prepare-bundle.ps1 -Destination F:\ -Include70B

# Override the model set entirely.
.\scripts\prepare-bundle.ps1 -Models gemma4:latest,granite4:tiny-h -Destination E:\

# Drop a PowerShell 7 MSI in the bundle for offline install on the workstation.
.\scripts\prepare-bundle.ps1 -Destination E:\ -IncludePowerShell7

# Already pulled the models and just want to rebuild + restage onto a new drive.
.\scripts\prepare-bundle.ps1 -SkipPull -Destination E:\
```

Defaults target an RTX 3070 (8 GB VRAM) plus a Xeon / 128 GB RAM workstation: a fully GPU-resident `qwen2.5:7b-instruct-q5_K_M` paired with a partial-offload `qwen2.5:14b-instruct-q4_K_M`. Total bundle is ~15 GB; with `-Include70B` it grows to ~57 GB (plan for a 64 GB+ drive).

### Manual flow

If you want finer control, the underlying script is `scripts\package-airgapped.ps1`:

```powershell
.venv\Scripts\Activate.ps1
.\scripts\package-airgapped.ps1
```

The script will:

1. Run `build.ps1` to produce the three PyInstaller one-folder bundles.
2. Copy the bundled Ollama runtime into the staging folder.
3. Read each requested model's manifest, follow it to the referenced
   blobs, and copy *only those* into `models\` -- your other locally
   pulled models stay out of the bundle, keeping size predictable.
4. Drop in `start-suite.ps1` and `README.txt`.
5. Print the bundle path and total size when done.

Output lands at:

```
dist\InscriptionSuite-Airgapped\
```

### Useful flags

```powershell
# Already built? Skip the long PyInstaller pass.
.\scripts\package-airgapped.ps1 -SkipBuild

# Different model set (only when you've changed the apps' DEFAULT_LLM_MODEL).
.\scripts\package-airgapped.ps1 -Models gemma4:latest,granite4:tiny-h

# Non-standard Ollama install.
.\scripts\package-airgapped.ps1 `
    -OllamaRoot "D:\Tools\Ollama" `
    -OllamaModelsRoot "D:\Tools\Ollama\.ollama\models"
```

---

## Transferring to the air-gapped workstation

1. Plug the USB drive into the offline workstation.
2. From inside `<USB>\InscriptionSuite-Airgapped\`, right-click
   `install.ps1` → **Run with PowerShell**.
3. The installer copies the bundle to
   `%LOCALAPPDATA%\Programs\InscriptionSuite\` and creates a Start
   Menu shortcut under `InscriptionSuite \ Inscription Suite`.
4. From here on, launch via Start Menu → **Inscription Suite**.
   (The shortcut runs the installed copy of `start-suite.ps1`, which
   self-elevates for UIA visibility into elevated forensic tools.)

If the workstation refuses to run the script with `UnauthorizedAccess`,
run this once as the local user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

This is per-user, doesn't need administrator, and only affects this account.

### Installer flags

```powershell
# Default: per-user install at %LOCALAPPDATA%\Programs\InscriptionSuite,
# Start Menu shortcut, no admin needed.
.\install.ps1

# Add a Desktop shortcut alongside the Start Menu one.
.\install.ps1 -DesktopShortcut

# Replace an existing install without prompting.
.\install.ps1 -Force

# System-wide install (right-click -> Run as administrator first).
.\install.ps1 -InstallRoot "C:\Program Files\InscriptionSuite"

# If the bundle was built with -IncludePowerShell7, also install PS 7.
.\install.ps1 -InstallPowerShell7
```

Re-running `install.ps1` only replaces the binaries. User configuration
(`%LOCALAPPDATA%\Inscription\`, `%LOCALAPPDATA%\CaseForge\`,
`%LOCALAPPDATA%\CaseGuide\`) and saved cases are kept intact.

---

## How the runtime stitches together

The launcher sets two environment variables before starting Ollama:

```powershell
$env:OLLAMA_MODELS = "<bundle>\models"
$env:OLLAMA_HOST   = "127.0.0.1:11434"
```

Then it spawns `<bundle>\ollama\ollama.exe serve` in the background and
polls `http://127.0.0.1:11434/api/tags` until it answers 200. After
that, the apps reach Ollama via their normal default base URL
(`http://localhost:11434/v1`) — no change to app config needed.

When more than one model is bundled, the launcher walks
`models\manifests\registry.ollama.ai\library\` to enumerate them, asks
the operator which to use this session, and exports
`SUITE_LLM_MODEL=<chosen>` before launching any app. Inscription and
CaseGuide both honour that variable as their default — the user can
still override per-app via Settings, where the model field is now an
editable dropdown populated from `/v1/models`.

Closing the launcher window stops the spawned Ollama process. The apps
continue to run if launched, but their AI features will fail until you
re-run `start-suite.ps1`.

---

## What we don't ship

- **Antivirus exemption.** Some AV products quarantine PyInstaller
  bundles by default. Have the workstation's AV admin allow-list the
  three `.exe` paths inside the bundle before first run.
- **Driver / runtime prerequisites for the host OS.** PyInstaller
  bundles include the Visual C++ runtime PySide6 needs; nothing else is
  required for the bundled software itself.
- **Model updates.** A new bundle is the upgrade path — the workstation
  has no path to pull a newer model on its own.
