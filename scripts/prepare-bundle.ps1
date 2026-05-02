<#
.SYNOPSIS
    Pull models, build the InscriptionSuite air-gapped bundle, and (optionally)
    stage it onto an external drive in one shot.

.DESCRIPTION
    On the connected build machine: pulls the requested LLM model tags via
    Ollama, runs package-airgapped.ps1 to assemble the bundle (apps +
    Ollama runtime + model blobs + launcher), and either leaves the bundle
    in dist\InscriptionSuite-Airgapped\ or copies it to a destination
    (e.g. an external drive) for transfer.

    Default model set targets an RTX 3070 (8 GB VRAM) plus a Xeon
    workstation with 128 GB RAM: a fully GPU-resident 7B at Q5_K_M alongside
    a partial-offload 14B at Q4_K_M, so the air-gapped operator can pick
    the right size for their immediate task at first launch.

.PARAMETER Destination
    Optional path to copy the finished bundle into. Typical use:
    -Destination E:\ or -Destination "F:\Forensic\". Leave empty to
    leave the bundle in the repo's dist\ directory.

.PARAMETER Models
    Override the default model set. Each entry must be a tag pullable
    via 'ollama pull'.

.PARAMETER Include70B
    Add llama3.3:70b-instruct-q4_K_M to the bundled models. Adds ~42 GB
    on top of the default ~14 GB. Only useful when the target workstation
    has 128 GB+ RAM and the operator is willing to wait ~3 min per
    rewrite.

.PARAMETER IncludePowerShell7
    Drop the latest PowerShell 7 win-x64 MSI installer next to start-suite.ps1
    inside the bundle. Optional -- the launcher works on PowerShell 5.1, but
    PS 7 is faster and reads UTF-8 by default.

.PARAMETER SkipPull
    Skip 'ollama pull' for each model. Use when the models are already
    in the local Ollama store and you only want to rebuild the bundle.

.PARAMETER SkipBuild
    Skip the package-airgapped.ps1 step. Use after a successful build
    when you only want to copy the existing bundle to a new destination.

.EXAMPLE
    .\scripts\prepare-bundle.ps1 -Destination E:\
    Pulls the default Qwen 7B + 14B, builds the bundle, copies onto E:\.

.EXAMPLE
    .\scripts\prepare-bundle.ps1 -Include70B -Destination F:\
    Adds llama3.3:70b-instruct on top. Output ~57 GB; plan for a 64 GB+ drive.

.EXAMPLE
    .\scripts\prepare-bundle.ps1 -Models gemma4:latest -SkipPull -Destination E:\
    Just rebuild + restage with a single already-pulled model.
#>
param(
    [string]$Destination = "",
    [string[]]$Models = @("qwen2.5:7b-instruct-q5_K_M", "qwen2.5:14b-instruct-q4_K_M"),
    [switch]$Include70B,
    [switch]$IncludePowerShell7,
    [switch]$SkipPull,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$RepoRoot  = Split-Path -Parent $PSScriptRoot
$BundleSrc = Join-Path $RepoRoot "dist\InscriptionSuite-Airgapped"

if ($Include70B -and ($Models -notcontains "llama3.3:70b-instruct-q4_K_M")) {
    $Models += "llama3.3:70b-instruct-q4_K_M"
}

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# 1. Sanity ------------------------------------------------------------------

Write-Step "Verifying Ollama is on PATH"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama not found. Install from https://ollama.com/download/windows first, then rerun."
}

# 2. Pull models -------------------------------------------------------------

if (-not $SkipPull) {
    foreach ($m in $Models) {
        Write-Step "Pulling $m"
        ollama pull $m
        if ($LASTEXITCODE -ne 0) {
            throw "ollama pull $m failed (exit $LASTEXITCODE). Check connectivity and try again."
        }
    }
} else {
    Write-Host "Skipping 'ollama pull' (per -SkipPull)" -ForegroundColor Yellow
}

# 3. Build the bundle --------------------------------------------------------

if (-not $SkipBuild) {
    Write-Step "Building air-gapped bundle ($($Models.Count) model(s))"
    & (Join-Path $PSScriptRoot "package-airgapped.ps1") -Models $Models
    if ($LASTEXITCODE -ne 0) {
        throw "package-airgapped.ps1 failed (exit $LASTEXITCODE)."
    }
} else {
    Write-Host "Skipping bundle build (per -SkipBuild)" -ForegroundColor Yellow
}

if (-not (Test-Path $BundleSrc)) {
    throw "Expected bundle at $BundleSrc but it does not exist. Did the build step run?"
}

# 4. Optional installers next to the launcher --------------------------------

if ($IncludePowerShell7) {
    Write-Step "Fetching the latest PowerShell 7 MSI"
    # Some Windows 10 boxes still default to TLS 1.0 -- GitHub's API
    # rejects that. Forcing 1.2 makes the download work everywhere.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    # Invoke-WebRequest's progress bar is so slow on PS 5.1 it dominates
    # the download time; suppress it for the duration of the fetch.
    $previousProgress = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    try {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/PowerShell/PowerShell/releases/latest"
        $asset = $release.assets | Where-Object { $_.name -like "PowerShell-*-win-x64.msi" } | Select-Object -First 1
        if (-not $asset) {
            throw "Could not locate a win-x64 MSI in the GitHub release manifest."
        }
        $dest = Join-Path $BundleSrc $asset.name
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest
        $sizeMB = [math]::Round($asset.size / 1MB, 1)
        Write-Host "  Saved $($asset.name) ($sizeMB MB)"
    } finally {
        $ProgressPreference = $previousProgress
    }
}

# 5. Copy to external drive --------------------------------------------------

if ($Destination) {
    if (-not (Test-Path $Destination)) {
        New-Item -ItemType Directory -Path $Destination | Out-Null
    }
    $destPath = Join-Path $Destination "InscriptionSuite-Airgapped"
    if (Test-Path $destPath) {
        Write-Step "Replacing existing $destPath"
        Remove-Item -Recurse -Force $destPath
    }
    Write-Step "Copying bundle to $destPath"
    Copy-Item -Recurse -Force $BundleSrc $destPath
    $finalPath = $destPath
} else {
    $finalPath = $BundleSrc
}

# 6. Report ------------------------------------------------------------------

$totalBytes = (Get-ChildItem -Recurse -File $finalPath | Measure-Object -Property Length -Sum).Sum
$totalGB = [math]::Round($totalBytes / 1GB, 2)

Write-Host ""
Write-Host "Bundle ready" -ForegroundColor Green
Write-Host "  Path: $finalPath" -ForegroundColor Green
Write-Host "  Size: $totalGB GB" -ForegroundColor Green
Write-Host ""
Write-Host "Next: take the folder to the air-gapped workstation and"
Write-Host "right-click install.ps1 -> Run with PowerShell. The installer"
Write-Host "copies the bundle to %LOCALAPPDATA%\Programs\InscriptionSuite,"
Write-Host "creates a Start Menu shortcut, and from then on the operator"
Write-Host "launches the suite via Start Menu -> Inscription Suite."
