#Requires -Version 5.1
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

# Force TLS 1.2 unconditionally. Windows Server 2012 R2 / 8.1 default
# their .NET ServicePointManager to TLS 1.0, which github.com no
# longer accepts -- any subsequent Invoke-RestMethod / Invoke-WebRequest
# in this script (PowerShell 7 download, future GitHub fetches) would
# fail with a cryptic "Could not create SSL/TLS secure channel" error.
# Setting it once at the top is a no-op on modern Windows where 1.2 is
# already the default, and a transparent fix on older boxes.
[Net.ServicePointManager]::SecurityProtocol =
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

if ($Include70B -and ($Models -notcontains "llama3.3:70b-instruct-q4_K_M")) {
    $Models += "llama3.3:70b-instruct-q4_K_M"
}

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# 1. Sanity ------------------------------------------------------------------
# Only require Ollama if we're actually going to invoke it. The
# -SkipPull -SkipBuild combo is the "stage an already-built bundle to
# a different drive" path; it doesn't touch Ollama at all and shouldn't
# block on a machine that doesn't have it.

if (-not $SkipPull) {
    Write-Step "Verifying Ollama is on PATH"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw "Ollama not found. Install from https://ollama.com/download/windows first, then rerun. (Use -SkipPull if your models are already pulled.)"
    }
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
    # Invoke-WebRequest's progress bar is so slow on PS 5.1 it dominates
    # the download time; suppress it for the duration of the fetch.
    $previousProgress = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    try {
        # -UseBasicParsing avoids the legacy IE rendering engine, which
        # may not be initialised on Server Core or locked-down workstations
        # and would otherwise throw "The response content cannot be parsed
        # because the Internet Explorer engine is not available".
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/PowerShell/PowerShell/releases/latest" -UseBasicParsing
        $asset = $release.assets | Where-Object { $_.name -like "PowerShell-*-win-x64.msi" } | Select-Object -First 1
        if (-not $asset) {
            throw "Could not locate a win-x64 MSI in the GitHub release manifest."
        }
        $dest = Join-Path $BundleSrc $asset.name
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest -UseBasicParsing
        $sizeMB = [math]::Round($asset.size / 1MB, 1)
        Write-Host "  Saved $($asset.name) ($sizeMB MB)"
    } finally {
        $ProgressPreference = $previousProgress
    }
}

# 5. Write version.json + manifest.json -------------------------------------
# Stamps the bundle with build provenance (git SHA + timestamp + model
# list) and a SHA-256 manifest of every file. install.ps1 verifies the
# manifest before copying onto the workstation so a bad USB transfer
# fails loudly instead of producing a silently-corrupt install.

Write-Step "Stamping version + writing SHA-256 manifest"

$gitSha = ""
$gitBranch = ""
try {
    $gitSha = (& git -C $RepoRoot rev-parse HEAD 2>$null).Trim()
    $gitBranch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null).Trim()
} catch {
    # Not a git checkout (or git not on PATH). Stamp as "unknown" so
    # the manifest is still useful, just less informative.
}
if (-not $gitSha) { $gitSha = "unknown" }
if (-not $gitBranch) { $gitBranch = "unknown" }

$buildTimestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$versionPath = Join-Path $BundleSrc "version.json"
$versionPayload = [ordered]@{
    bundle_format_version = 1
    build_timestamp       = $buildTimestamp
    git_sha               = $gitSha
    git_branch            = $gitBranch
    models                = @($Models)
}
$versionPayload | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath $versionPath -Encoding utf8

# Hash every file in the bundle except manifest.json itself (chicken-
# and-egg) and version.json (already finalised, will be hashed below).
# Drive the walk off Get-ChildItem so we naturally pick up nested
# files like models\blobs\sha256-* and Inscription\_internal\... .
$manifestPath = Join-Path $BundleSrc "manifest.json"
$files = Get-ChildItem -LiteralPath $BundleSrc -Recurse -File |
    Where-Object { $_.FullName -ne $manifestPath } |
    Sort-Object FullName

$manifestEntries = [ordered]@{}
$bundleRootLength = $BundleSrc.TrimEnd('\').Length + 1  # +1 for separator
$hashed = 0
foreach ($file in $files) {
    $rel = $file.FullName.Substring($bundleRootLength).Replace('\', '/')
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLower()
    $manifestEntries[$rel] = "sha256:$hash"
    $hashed++
}

$manifestPayload = [ordered]@{
    manifest_version = 1
    git_sha          = $gitSha
    created_at       = $buildTimestamp
    files            = $manifestEntries
}
$manifestPayload | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath $manifestPath -Encoding utf8

Write-Host "  version.json: git $gitSha (branch $gitBranch)"
Write-Host "  manifest.json: $hashed files hashed"

# 6. Copy to external drive --------------------------------------------------

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

# 7. Report ------------------------------------------------------------------

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
