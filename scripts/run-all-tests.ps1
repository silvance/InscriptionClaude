<#
.SYNOPSIS
    Run pytest against all four test suites in sequence.

.DESCRIPTION
    Invokes pytest separately inside each app's directory so each
    app's pyproject.toml [tool.pytest.ini_options] is honoured (the
    src-layout discovery, marker definitions, etc.). Returns
    non-zero if any suite fails, with a summary at the end so a CI
    job logs all failures rather than stopping at the first one.

    Why not a single 'pytest' invocation from the repo root? Each
    app's tests/ directory used to share the package name 'tests',
    which caused the conftest collision
        ImportPathMismatchError: ('tests.conftest', ...)
    The empty tests/__init__.py files have been dropped so the
    collision is gone, but the per-app pyproject.toml configs are
    still only loaded when pytest's rootdir is inside that app --
    so we cd in and invoke per-app to keep all the config intact.

.EXAMPLE
    .\scripts\run-all-tests.ps1
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Suites = @("suite_common", "inscription", "caseforge", "caseguide")
$env:QT_QPA_PLATFORM = "offscreen"

$failed = @()
foreach ($suite in $Suites) {
    Write-Host ""
    Write-Host "=== $suite ===" -ForegroundColor Cyan
    Push-Location (Join-Path $RepoRoot $suite)
    try {
        python -m pytest tests
        if ($LASTEXITCODE -ne 0) {
            $failed += $suite
        }
    } finally {
        Pop-Location
    }
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "FAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "All suites passed." -ForegroundColor Green
