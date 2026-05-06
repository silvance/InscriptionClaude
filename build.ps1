<#
.SYNOPSIS
    Build Inscription, CaseForge, and CaseGuide as standalone Windows executables.

.DESCRIPTION
    Runs PyInstaller for each sub-package and places the one-folder bundles at:
        inscription\dist\Inscription\Inscription.exe
        caseforge\dist\CaseForge\CaseForge.exe
        caseguide\dist\CaseGuide\CaseGuide.exe

    Prerequisites -- from the repo root, activate the shared venv then run:
        .\.venv\Scripts\Activate.ps1
        python -m pip install -e suite_common -e inscription[dev] -e caseforge[dev] -e caseguide[dev]
        .\build.ps1

    The [dev] extras include PyInstaller; without them the script will fail
    with "pyinstaller : The term 'pyinstaller' is not recognized". The
    suite_common package is the shared LLM client + JSON helpers all three
    apps depend on.

.PARAMETER App
    Which app to build: 'inscription', 'caseforge', 'caseguide', or 'all'.
    Defaults to 'all'.

.PARAMETER Clean
    Delete each dist\ directory before building.

.EXAMPLE
    .\build.ps1
    .\build.ps1 -App inscription -Clean
#>
param(
    [ValidateSet("inscription", "caseforge", "caseguide", "all")]
    [string]$App = "all",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

function Show-SetupHelp {
    param([string]$Reason)
    Write-Host ""
    Write-Host "ERROR: $Reason" -ForegroundColor Red
    Write-Host ""
    Write-Host "Activate the venv and install the [dev] extras (which include PyInstaller):"
    if (Test-Path "$RepoRoot\.venv\Scripts\Activate.ps1") {
        Write-Host "    Set-Location $RepoRoot"
        Write-Host "    .\.venv\Scripts\Activate.ps1"
        Write-Host "    python -m pip install -e suite_common ``"
        Write-Host "        -e inscription[dev] -e caseforge[dev] -e caseguide[dev]"
    } else {
        Write-Host "    Set-Location $RepoRoot"
        Write-Host "    py -3.12 -m venv .venv"
        Write-Host "    .\.venv\Scripts\Activate.ps1"
        Write-Host "    python -m pip install -e suite_common ``"
        Write-Host "        -e inscription[dev] -e caseforge[dev] -e caseguide[dev]"
    }
    exit 1
}

# Bail early when the env can't run PyInstaller, printing the exact
# commands to fix it. Order matters: PyInstaller importing is the
# only thing the build actually requires. Venv-active and Python-
# version checks are *guidance* for the dominant local-checkout
# failure mode, but they must NOT reject a working setup -- CI
# installs Python via actions/setup-python without a venv, and any
# contributor with an unconventional setup (conda, pyenv, system-
# Python pip --user) has likely got PyInstaller importable already.
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Show-SetupHelp -Reason "'python' is not on PATH."
}

# Fast accept: PyInstaller already importable -> we're set up.
& python -c "import PyInstaller" 2>$null
$pyinstallerImports = ($LASTEXITCODE -eq 0)
if (-not $pyinstallerImports) {
    # PyInstaller missing -- now graduate the guidance based on
    # how the environment looks.
    $pyVersion = & python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>$null
    if (-not $pyVersion) {
        Show-SetupHelp -Reason "Could not determine Python version."
    }
    $parts = $pyVersion -split "\."
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 12)) {
        Show-SetupHelp -Reason "Python 3.12+ required, found $pyVersion."
    }
    if (-not $env:VIRTUAL_ENV) {
        Show-SetupHelp -Reason "PyInstaller is not installed and no virtual environment is active."
    }
    Show-SetupHelp -Reason "PyInstaller is not installed in the active venv ($env:VIRTUAL_ENV)."
}

function Invoke-Build {
    param(
        [string]$SubDir,
        [string]$SpecName,
        [string]$Label
    )

    $target = Join-Path $RepoRoot $SubDir
    Write-Host ""
    Write-Host "=== Building $Label ===" -ForegroundColor Cyan

    Push-Location $target
    try {
        if ($Clean -and (Test-Path "dist")) {
            Write-Host "  Removing dist\..." -ForegroundColor Yellow
            Remove-Item -Recurse -Force "dist"
        }
        # Invoke through `python -m` so we don't depend on the
        # pip-installed Scripts directory being on PATH. Bare `pyinstaller`
        # works in a developer venv but trips on bare GitHub-Actions
        # Windows runners where Scripts\ may not be picked up by
        # PowerShell at the time this runs.
        python -m PyInstaller "packaging\$SpecName" --noconfirm
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller exited with code $LASTEXITCODE for $Label"
        }
    }
    finally {
        Pop-Location
    }

    Write-Host "=== ${Label}: OK ===" -ForegroundColor Green
}

$builds = @(
    [pscustomobject]@{ Dir = "inscription"; Spec = "inscription.spec"; Label = "Inscription" },
    [pscustomobject]@{ Dir = "caseforge";   Spec = "caseforge.spec";   Label = "CaseForge"   },
    [pscustomobject]@{ Dir = "caseguide";   Spec = "caseguide.spec";   Label = "CaseGuide"   }
)

foreach ($b in $builds) {
    if ($App -eq "all" -or $App -eq $b.Dir) {
        Invoke-Build -SubDir $b.Dir -SpecName $b.Spec -Label $b.Label
    }
}

Write-Host ""
Write-Host "Build complete." -ForegroundColor Cyan
foreach ($b in $builds) {
    if ($App -eq "all" -or $App -eq $b.Dir) {
        $exe = Join-Path $RepoRoot "$($b.Dir)\dist\$($b.Label)\$($b.Label).exe"
        if (Test-Path $exe) {
            Write-Host "  $exe" -ForegroundColor Green
        }
    }
}
