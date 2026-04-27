<#
.SYNOPSIS
    Build Inscription, CaseForge, and CaseGuide as standalone Windows executables.

.DESCRIPTION
    Runs PyInstaller for each sub-package and places the one-folder bundles at:
        inscription\dist\Inscription\Inscription.exe
        caseforge\dist\CaseForge\CaseForge.exe
        caseguide\dist\CaseGuide\CaseGuide.exe

    Prerequisites — from the repo root, activate the shared venv then run:
        .\.venv\Scripts\Activate.ps1
        .\build.ps1

    If each sub-package has its own venv, activate the appropriate one before
    passing -App to build individually.

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
        pyinstaller "packaging\$SpecName" --noconfirm
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
