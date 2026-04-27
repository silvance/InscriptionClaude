<#
.SYNOPSIS
    First-run launcher for the air-gapped Inscription suite bundle.

.DESCRIPTION
    Lives at the root of the InscriptionSuite-Airgapped folder. It:
        1. Points Ollama at the bundled models directory.
        2. Starts the bundled Ollama server on 127.0.0.1:11434.
        3. Waits until /api/tags answers 200.
        4. Opens a small picker so the operator can launch
           Inscription, CaseForge, or CaseGuide.

    Quitting the picker stops the Ollama server. Re-run this script to
    bring everything back up.
#>

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

# --------------------------------------------------------------- environment

$env:OLLAMA_MODELS = Join-Path $Root "models"
$env:OLLAMA_HOST   = "127.0.0.1:11434"
# Pin the data directory too so a previous Ollama install on this machine
# doesn't have us writing into its blobs folder by accident.
$env:OLLAMA_KEEP_ALIVE = "10m"

$ollamaExe = Join-Path $Root "ollama\ollama.exe"
if (-not (Test-Path $ollamaExe)) {
    Write-Error "Bundled ollama.exe not found at $ollamaExe. The bundle is incomplete."
    exit 1
}

# Already serving? Reuse it. Otherwise start fresh in a hidden window.
function Test-OllamaUp {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 1 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

$ourProcess = $null
if (Test-OllamaUp) {
    Write-Host "Ollama is already responding on 127.0.0.1:11434 — reusing it." -ForegroundColor Yellow
} else {
    Write-Host "Starting bundled Ollama server…" -ForegroundColor Cyan
    $ourProcess = Start-Process -FilePath $ollamaExe `
        -ArgumentList "serve" `
        -WindowStyle Hidden `
        -PassThru

    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if (Test-OllamaUp) { break }
    }
    if (-not (Test-OllamaUp)) {
        Write-Error "Ollama did not become ready within 60s. Check that ollama.exe runs on this machine."
        if ($ourProcess) { Stop-Process -Id $ourProcess.Id -Force -ErrorAction SilentlyContinue }
        exit 1
    }
    Write-Host "Ollama ready." -ForegroundColor Green
}

# ----------------------------------------------------------------- the menu

$apps = @(
    @{ Key = "1"; Label = "Inscription (capture a workflow)";    Exe = "Inscription\Inscription.exe" }
    @{ Key = "2"; Label = "CaseForge (case intake / report)";    Exe = "CaseForge\CaseForge.exe"     }
    @{ Key = "3"; Label = "CaseGuide (suggestion coach)";        Exe = "CaseGuide\CaseGuide.exe"     }
)

try {
    while ($true) {
        Write-Host ""
        Write-Host "Inscription suite — air-gapped" -ForegroundColor Cyan
        Write-Host "==============================" -ForegroundColor Cyan
        foreach ($a in $apps) {
            Write-Host ("  [{0}] {1}" -f $a.Key, $a.Label)
        }
        Write-Host "  [Q] Quit (also stops the bundled Ollama server)"
        Write-Host ""
        $choice = Read-Host "Pick"

        if ($choice -ieq "q") { break }

        $picked = $apps | Where-Object { $_.Key -eq $choice }
        if (-not $picked) {
            Write-Host "Unknown selection: $choice" -ForegroundColor Yellow
            continue
        }
        $exe = Join-Path $Root $picked.Exe
        if (-not (Test-Path $exe)) {
            Write-Host "Missing $exe — bundle is incomplete." -ForegroundColor Red
            continue
        }
        Start-Process -FilePath $exe
    }
} finally {
    if ($ourProcess -and -not $ourProcess.HasExited) {
        Write-Host "Stopping bundled Ollama server…" -ForegroundColor Cyan
        Stop-Process -Id $ourProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
