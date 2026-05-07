#Requires -Version 5.1
<#
.SYNOPSIS
    One-click build of the air-gapped Inscription Suite USB bundle.

.DESCRIPTION
    Wraps the existing prepare-bundle.ps1 with a friendlier UX so
    lab admins don't have to remember terminal flags between bundle
    refreshes. Designed to be invoked by Build-Bundle.bat in the
    repo root (double-click), but works as a normal script too.

    Lifecycle:
      1. First run on a fresh checkout: creates ``.venv`` with
         Python 3.12+, installs the four packages editable with
         their [dev] extras (which include PyInstaller). Skipped
         on subsequent runs.
      2. Verifies Ollama is on PATH. If not, opens a message box
         pointing at https://ollama.com/download/windows and exits.
      3. Pops a Windows Forms folder-picker for the USB drive
         (-Destination skips the picker).
      4. Calls scripts\prepare-bundle.ps1 with sensible defaults:
         pulls the standard model set, builds, writes the bundle
         straight to the destination (no doubled-disk staging),
         includes the PowerShell 7 MSI alongside.
      5. Shows a "Bundle ready" dialog with the path so the operator
         can copy/Eject and walk it to the air-gapped workstation.

.PARAMETER Destination
    Skip the folder picker and stage to this path directly. Useful
    for scripted re-builds. The bundle ends up at
    ``<Destination>\InscriptionSuite-Airgapped\``.

.PARAMETER SkipSetup
    Skip the venv create/install step even on a fresh checkout.
    Use when you've already set up the env manually.
#>
param(
    [string]$Destination = "",
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"
$ScriptRoot = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ScriptRoot

# Force TLS 1.2 for any network calls (mirrors prepare-bundle.ps1).
[Net.ServicePointManager]::SecurityProtocol =
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Show-Info([string]$Title, [string]$Body, [string]$Icon = "Information") {
    [System.Windows.Forms.MessageBox]::Show(
        $Body, $Title, [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::$Icon
    ) | Out-Null
}

function Show-Error([string]$Title, [string]$Body) {
    Show-Info -Title $Title -Body $Body -Icon "Error"
}

# 1. First-run setup ---------------------------------------------------------

$venvDir = Join-Path $RepoRoot ".venv"
$venvActivate = Join-Path $venvDir "Scripts\Activate.ps1"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvActivate) -and -not $SkipSetup) {
    Write-Step "First-run setup: creating .venv (this only happens once)"

    # Find a Python 3.12+ to bootstrap the venv. py.exe is the launcher
    # the official Python.org installer drops at C:\Windows\py.exe.
    $bootstrap = $null
    foreach ($candidate in @(
        @("py", "-3.12"),
        @("py", "-3.13"),
        @("python3.12"),
        @("python3"),
        @("python")
    )) {
        try {
            $verRaw = & $candidate[0] $candidate[1..($candidate.Count - 1)] -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
            if ($verRaw) {
                $verParts = ($verRaw.Trim()) -split "\."
                if ([int]$verParts[0] -ge 3 -and [int]$verParts[1] -ge 12) {
                    $bootstrap = $candidate
                    break
                }
            }
        } catch {
            continue
        }
    }
    if (-not $bootstrap) {
        Show-Error -Title "Inscription Suite -- Build Bundle" -Body @"
Python 3.12+ was not found on this machine.

Install Python from https://www.python.org/downloads/windows/
(make sure to tick "Add Python to PATH" during install), then
double-click Build-Bundle.bat again.
"@
        exit 1
    }
    Write-Host "  Bootstrap interpreter: $($bootstrap -join ' ')"

    & $bootstrap[0] $bootstrap[1..($bootstrap.Count - 1)] -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Show-Error -Title "Inscription Suite -- Build Bundle" -Body "Failed to create .venv. See the console window for details."
        exit 1
    }

    Write-Step "Installing the four packages editable + [dev] extras"
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install `
        -e (Join-Path $RepoRoot "suite_common") `
        -e ((Join-Path $RepoRoot "inscription") + "[dev]") `
        -e ((Join-Path $RepoRoot "caseforge") + "[dev]") `
        -e ((Join-Path $RepoRoot "caseguide") + "[dev]")
    if ($LASTEXITCODE -ne 0) {
        Show-Error -Title "Inscription Suite -- Build Bundle" -Body "pip install failed. See the console window for details."
        exit 1
    }
    Write-Host "  .venv ready." -ForegroundColor Green
}

# 2. Activate the venv for the rest of this process. -----------------------

if (-not (Test-Path $venvActivate)) {
    Show-Error -Title "Inscription Suite -- Build Bundle" -Body @"
.venv missing at $venvDir, and -SkipSetup was passed.

Drop -SkipSetup or create the venv manually first (see SETUP.md).
"@
    exit 1
}
. $venvActivate

# 3. Verify Ollama is on PATH ----------------------------------------------

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Show-Error -Title "Inscription Suite -- Build Bundle" -Body @"
Ollama is not installed on this machine.

Download the Windows installer from
https://ollama.com/download/windows, install it, then double-click
Build-Bundle.bat again. The bundle pulls its model weights via Ollama,
so it has to be present on the build machine (the air-gapped target
gets the bundled copy).
"@
    exit 1
}

# 4. Pick the destination drive --------------------------------------------

if (-not $Destination) {
    $picker = New-Object System.Windows.Forms.FolderBrowserDialog
    $picker.Description = "Pick the USB drive (or folder) where the bundle will be staged"
    $picker.ShowNewFolderButton = $true
    if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
    $Destination = $picker.SelectedPath
}

# 5. Build the bundle ------------------------------------------------------
# prepare-bundle.ps1 handles the FAT32 pre-flight, in-place staging,
# manifest writing, and PowerShell 7 MSI inclusion. We just hand it
# the destination and let it run with sensible defaults.

Write-Step "Building bundle to $Destination"
& (Join-Path $ScriptRoot "prepare-bundle.ps1") `
    -Destination $Destination `
    -IncludePowerShell7
if ($LASTEXITCODE -ne 0) {
    Show-Error -Title "Inscription Suite -- Build Bundle" -Body @"
Bundle build failed. The console window above has the full output;
common causes are FAT32 destinations (reformat as exFAT), no internet
on the build machine (Ollama needs to fetch model manifests), or
disk space on the destination.
"@
    exit 1
}

# 6. Final report ---------------------------------------------------------

$bundlePath = Join-Path $Destination "InscriptionSuite-Airgapped"
Show-Info -Title "Inscription Suite -- Build Bundle" -Body @"
Bundle ready at:

$bundlePath

Eject the USB drive and take it to the air-gapped workstation.
On the target, double-click Install-Suite.cmd inside the bundle
folder for a one-click install.
"@
