#Requires -Version 5.1
<#
.SYNOPSIS
    Produce a self-contained InscriptionSuite folder for air-gapped deployment.

.DESCRIPTION
    Output: dist\InscriptionSuite-Airgapped\ -- copy the whole folder to a USB
    stick, drop it onto the air-gapped workstation, and double-click
    start-suite.ps1.

    The bundle contains:
        Inscription\         -- Inscription one-folder PyInstaller bundle
        CaseForge\           -- CaseForge one-folder bundle
        CaseGuide\           -- CaseGuide one-folder bundle
        ollama\              -- Bundled Ollama Windows runtime (ollama.exe + libs)
        models\              -- Pre-pulled Ollama model blobs and manifests
        start-suite.ps1      -- First-run launcher (starts Ollama, opens menu)
        README.txt           -- Operator notes for the destination machine

    Prerequisites on this (connected) machine:
        - Windows 10/11 with PowerShell.
        - Activated venv with all four packages installed editable
          (see SETUP.md).
        - Ollama installed and on PATH.
        - The default models already pulled:
              ollama pull gemma4:latest
              ollama pull granite4:tiny-h

.PARAMETER Models
    Models to bundle. Defaults to the suite default plus a smaller
    fallback so the air-gapped operator can switch via start-suite.ps1
    when the workstation can't fit gemma4 in memory. Override here if
    you'd rather ship a different set.

.PARAMETER OllamaRoot
    Where the user's Ollama binaries live on this machine. Default is the
    standard installer location.

.PARAMETER OllamaModelsRoot
    Where the user's pulled model blobs live on this machine. Default is
    the standard Ollama models directory.

.PARAMETER OutputRoot
    Parent directory for the staged bundle. The script writes to
    "<OutputRoot>\InscriptionSuite-Airgapped\". Defaults to
    "<repo>\dist\". Set this to a roomy drive (or directly to the
    USB drive) to avoid the doubled disk requirement of staging
    locally and then copying.

.PARAMETER SkipBuild
    Skip running build.ps1; assume dist\ folders are already present.

.EXAMPLE
    .\scripts\package-airgapped.ps1
    .\scripts\package-airgapped.ps1 -Models gemma4:latest -SkipBuild
    .\scripts\package-airgapped.ps1 -OutputRoot E:\
#>
param(
    [string[]]$Models = @("gemma4:latest", "granite4:tiny-h"),
    [string]$OllamaRoot = "$env:LOCALAPPDATA\Programs\Ollama",
    [string]$OllamaModelsRoot = "$env:USERPROFILE\.ollama\models",
    [string]$OutputRoot = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ($OutputRoot) {
    if (-not (Test-Path $OutputRoot)) {
        New-Item -ItemType Directory -Path $OutputRoot | Out-Null
    }
    $BundleRoot = Join-Path $OutputRoot "InscriptionSuite-Airgapped"
} else {
    $BundleRoot = Join-Path $RepoRoot "dist\InscriptionSuite-Airgapped"
}

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# 1. Sanity checks ----------------------------------------------------------

Write-Step "Verifying prerequisites"

if (-not (Test-Path $OllamaRoot)) {
    throw "Ollama not found at $OllamaRoot. Install Ollama from https://ollama.com/download/windows on this machine first, or pass -OllamaRoot."
}
if (-not (Test-Path $OllamaModelsRoot)) {
    throw "Ollama models directory not found at $OllamaModelsRoot. Run 'ollama pull <model>' on this machine first, or pass -OllamaModelsRoot."
}
foreach ($m in $Models) {
    $parts = $m -split ":", 2
    $name = $parts[0]
    $tag  = if ($parts.Count -gt 1) { $parts[1] } else { "latest" }
    $manifestPath = Join-Path $OllamaModelsRoot "manifests\registry.ollama.ai\library\$name\$tag"
    if (-not (Test-Path $manifestPath)) {
        throw "Model '$m' is not pulled on this machine. Run 'ollama pull $m' and rerun this script."
    }
}

# 2. Build the three .exe bundles -------------------------------------------

if (-not $SkipBuild) {
    Write-Step "Building Inscription / CaseForge / CaseGuide"
    & (Join-Path $RepoRoot "build.ps1")
} else {
    Write-Host "  Skipping build (per -SkipBuild)" -ForegroundColor Yellow
}

# 3. Reset the bundle output directory --------------------------------------

Write-Step "Staging bundle at $BundleRoot"
if (Test-Path $BundleRoot) {
    Remove-Item -Recurse -Force $BundleRoot
}
New-Item -ItemType Directory -Path $BundleRoot | Out-Null

# 4. Copy each app's one-folder bundle --------------------------------------

$apps = @(
    @{ Source = "inscription\dist\Inscription"; Name = "Inscription" }
    @{ Source = "caseforge\dist\CaseForge";     Name = "CaseForge"   }
    @{ Source = "caseguide\dist\CaseGuide";     Name = "CaseGuide"   }
)
foreach ($app in $apps) {
    $src = Join-Path $RepoRoot $app.Source
    if (-not (Test-Path $src)) {
        throw "Build output missing: $src. Re-run build.ps1 (drop -SkipBuild)."
    }
    Write-Host "  Copying $($app.Name)..."
    Copy-Item -Recurse -Force $src (Join-Path $BundleRoot $app.Name)
}

# 5. Copy Ollama Windows runtime --------------------------------------------

Write-Step "Bundling Ollama runtime from $OllamaRoot"
$ollamaDest = Join-Path $BundleRoot "ollama"
Copy-Item -Recurse -Force $OllamaRoot $ollamaDest

# 6. Copy only the requested model blobs + manifests ------------------------

Write-Step "Bundling model blobs (only the requested models, to keep size down)"
$modelsDest = Join-Path $BundleRoot "models"
New-Item -ItemType Directory -Path (Join-Path $modelsDest "blobs") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $modelsDest "manifests\registry.ollama.ai\library") | Out-Null

$digestsToCopy = New-Object System.Collections.Generic.HashSet[string]

foreach ($m in $Models) {
    $parts = $m -split ":", 2
    $name = $parts[0]
    $tag  = if ($parts.Count -gt 1) { $parts[1] } else { "latest" }

    $srcManifest  = Join-Path $OllamaModelsRoot "manifests\registry.ollama.ai\library\$name\$tag"
    $destManifestDir = Join-Path $modelsDest "manifests\registry.ollama.ai\library\$name"
    if (-not (Test-Path $destManifestDir)) {
        New-Item -ItemType Directory -Path $destManifestDir | Out-Null
    }
    Copy-Item -Force $srcManifest (Join-Path $destManifestDir $tag)

    $manifest = Get-Content $srcManifest -Raw | ConvertFrom-Json
    if ($manifest.config -and $manifest.config.digest) {
        [void]$digestsToCopy.Add($manifest.config.digest)
    }
    foreach ($layer in $manifest.layers) {
        if ($layer.digest) { [void]$digestsToCopy.Add($layer.digest) }
    }
    Write-Host "  $m -> manifest staged, $($manifest.layers.Count) layers referenced"
}

$blobCount = 0
foreach ($digest in $digestsToCopy) {
    # Manifests use 'sha256:abc'; on disk they're 'sha256-abc'.
    $blobName = $digest -replace '^sha256:', 'sha256-'
    $srcBlob  = Join-Path $OllamaModelsRoot "blobs\$blobName"
    if (-not (Test-Path $srcBlob)) {
        throw "Manifest references blob $digest but the blob is missing at $srcBlob. Re-run 'ollama pull' for the affected model."
    }
    Copy-Item -Force $srcBlob (Join-Path $modelsDest "blobs\$blobName")
    $blobCount++
}
Write-Host "  Copied $blobCount unique blobs."

# 7. Drop in the launcher script + installer + README ----------------------

Write-Step "Writing start-suite.ps1, install.ps1, and README.txt"

$startScript = Join-Path $PSScriptRoot "templates\start-suite.ps1"
if (-not (Test-Path $startScript)) {
    throw "Launcher template missing at $startScript. The repository may be incomplete."
}
Copy-Item -Force $startScript (Join-Path $BundleRoot "start-suite.ps1")

$installScript = Join-Path $PSScriptRoot "templates\install.ps1"
if (-not (Test-Path $installScript)) {
    throw "Installer template missing at $installScript. The repository may be incomplete."
}
Copy-Item -Force $installScript (Join-Path $BundleRoot "install.ps1")

$readme = Join-Path $PSScriptRoot "templates\airgapped-README.txt"
if (Test-Path $readme) {
    Copy-Item -Force $readme (Join-Path $BundleRoot "README.txt")
}

# 8. Report --------------------------------------------------------------

$totalBytes = (Get-ChildItem -Recurse -File $BundleRoot | Measure-Object -Property Length -Sum).Sum
$totalGB = [math]::Round($totalBytes / 1GB, 2)

Write-Host ""
Write-Host "Bundle ready at:" -ForegroundColor Green
Write-Host "  $BundleRoot" -ForegroundColor Green
Write-Host "  Total size: $totalGB GB" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Copy the whole folder to a USB drive."
Write-Host "  2. On the air-gapped workstation, copy it anywhere you have write access."
Write-Host "  3. Double-click start-suite.ps1 (or right-click -> Run with PowerShell)."
