# Inscription dev helper.
#
# Usage:
#   .\scripts\dev.ps1                  # runs lint + typecheck + test
#   .\scripts\dev.ps1 install          # install package with dev extras
#   .\scripts\dev.ps1 lint             # ruff check
#   .\scripts\dev.ps1 format           # ruff format (writes changes)
#   .\scripts\dev.ps1 format-check     # ruff format --check (read-only)
#   .\scripts\dev.ps1 typecheck        # mypy strict
#   .\scripts\dev.ps1 test             # pytest with coverage
#   .\scripts\dev.ps1 run              # launch the app from source
#   .\scripts\dev.ps1 build            # build one-folder exe with PyInstaller
#   .\scripts\dev.ps1 clean            # remove build artefacts and caches
#   .\scripts\dev.ps1 all              # lint + typecheck + test (CI parity)

param(
    [Parameter(Mandatory = $false, Position = 0)]
    [ValidateSet(
        'install', 'lint', 'format', 'format-check', 'typecheck',
        'test', 'run', 'build', 'clean', 'all'
    )]
    [string]$Command = 'all'
)

$ErrorActionPreference = 'Stop'

function Step([string]$name, [ScriptBlock]$block) {
    Write-Host ""
    Write-Host ">>> $name" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE -ne 0) {
        throw "$name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Install {
    Step "pip install -e .[dev]" {
        python -m pip install --upgrade pip
        python -m pip install -e ".[dev]"
    }
}

function Invoke-Lint {
    Step "ruff check" { ruff check src tests }
}

function Invoke-Format {
    Step "ruff format" { ruff format src tests }
}

function Invoke-FormatCheck {
    Step "ruff format --check" { ruff format --check src tests }
}

function Invoke-Typecheck {
    Step "mypy (strict)" { mypy src tests }
}

function Invoke-Test {
    $env:QT_QPA_PLATFORM = 'offscreen'
    Step "pytest" {
        pytest --cov=inscription --cov-report=term
    }
}

function Invoke-Run {
    Step "python -m inscription" { python -m inscription }
}

function Invoke-Build {
    Step "pyinstaller" {
        pyinstaller packaging/inscription.spec --noconfirm
    }
    Write-Host ""
    Write-Host "Build output: dist\Inscription\Inscription.exe" -ForegroundColor Green
}

function Invoke-Clean {
    $targets = @(
        'build', 'dist', '.pytest_cache', '.mypy_cache', '.ruff_cache',
        'coverage.xml', '.coverage', 'htmlcov'
    )
    foreach ($t in $targets) {
        if (Test-Path $t) {
            Remove-Item -Recurse -Force $t
            Write-Host "removed $t"
        }
    }
    Get-ChildItem -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-Item -Recurse -Force $_.FullName
            Write-Host "removed $($_.FullName)"
        }
    Get-ChildItem -Recurse -Directory -Filter '*.egg-info' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-Item -Recurse -Force $_.FullName
            Write-Host "removed $($_.FullName)"
        }
}

switch ($Command) {
    'install'      { Invoke-Install }
    'lint'         { Invoke-Lint }
    'format'       { Invoke-Format }
    'format-check' { Invoke-FormatCheck }
    'typecheck'    { Invoke-Typecheck }
    'test'         { Invoke-Test }
    'run'          { Invoke-Run }
    'build'        { Invoke-Build }
    'clean'        { Invoke-Clean }
    'all' {
        Invoke-Lint
        Invoke-FormatCheck
        Invoke-Typecheck
        Invoke-Test
        Write-Host ""
        Write-Host "All checks passed." -ForegroundColor Green
    }
}
