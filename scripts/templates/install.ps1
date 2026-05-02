<#
.SYNOPSIS
    Install the air-gapped Inscription suite bundle to a permanent location
    on this workstation.

.DESCRIPTION
    Run from inside the bundle directory (e.g. E:\InscriptionSuite-Airgapped\)
    on the offline workstation. Copies the whole bundle to a stable path,
    creates a Start Menu entry that launches start-suite.ps1, and
    (optionally) installs the bundled PowerShell 7 MSI.

    No admin required for the default per-user install. Pointing
    -InstallRoot at C:\Program Files\InscriptionSuite\ requires admin --
    right-click install.ps1 -> Run as administrator first.

    User configuration / saved cases are NOT touched -- those live
    under %LOCALAPPDATA%\Inscription\, %LOCALAPPDATA%\CaseGuide\,
    %LOCALAPPDATA%\CaseForge\, and wherever the operator chose to keep
    case folders. Re-running the installer with -Force overwrites the
    binaries but preserves all of that.

.PARAMETER InstallRoot
    Where to install. Default: %LOCALAPPDATA%\Programs\InscriptionSuite.
    Use C:\InscriptionSuite or C:\Program Files\InscriptionSuite for a
    multi-user install (those need admin).

.PARAMETER Force
    Wipe an existing install at $InstallRoot without prompting.

.PARAMETER DesktopShortcut
    Also drop a Desktop shortcut. Start Menu shortcut is always created.

.PARAMETER InstallPowerShell7
    If a PowerShell-*-win-x64.msi file is present in the bundle (added
    at bundle time via prepare-bundle.ps1 -IncludePowerShell7), launch
    its installer with /qb (basic UI). Skipped silently when no MSI
    is present.

.EXAMPLE
    .\install.ps1
    Default per-user install with a Start Menu shortcut.

.EXAMPLE
    .\install.ps1 -DesktopShortcut -InstallPowerShell7
    Per-user install plus desktop shortcut and PS7 (if the MSI was
    bundled in via -IncludePowerShell7 on the build side).

.EXAMPLE
    .\install.ps1 -InstallRoot "C:\InscriptionSuite" -Force
    System-wide install. Right-click -> Run as administrator first.
#>
param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\Programs\InscriptionSuite",
    [switch]$Force,
    [switch]$DesktopShortcut,
    [switch]$InstallPowerShell7
)

$ErrorActionPreference = "Stop"
$BundleSrc = $PSScriptRoot

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# Normalise InstallRoot so relative paths and trailing slashes don't bite
# the source/destination overlap check below. GetFullPath without a base
# resolves relative to the process's current directory.
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)

# 1. Verify we are inside a real bundle --------------------------------------

Write-Step "Checking bundle integrity"
$expected = @("Inscription", "CaseForge", "CaseGuide", "ollama", "models", "start-suite.ps1")
foreach ($item in $expected) {
    if (-not (Test-Path (Join-Path $BundleSrc $item))) {
        throw "install.ps1 must run from inside the bundle directory. Missing: $item. Are you inside InscriptionSuite-Airgapped\?"
    }
}
Write-Host "  Bundle source: $BundleSrc"

# 1a. Refuse same/overlapping source and destination ------------------------
# Stops "right-click install.ps1 from inside an existing install" from
# wiping the bundle out from under itself.
$bundleResolved = (Resolve-Path -LiteralPath $BundleSrc).Path.TrimEnd('\')
$installNormalised = $InstallRoot.TrimEnd('\')
if ($bundleResolved -ieq $installNormalised) {
    throw "Source ($BundleSrc) and -InstallRoot ($InstallRoot) are the same path. Re-run install.ps1 from the original bundle (e.g. on USB), or pass a different -InstallRoot."
}
if ($installNormalised -like ($bundleResolved + '\*') -or $bundleResolved -like ($installNormalised + '\*')) {
    throw "Source ($BundleSrc) and -InstallRoot ($InstallRoot) overlap. Pick a destination that is not a subdirectory of the bundle (and vice versa)."
}

# 2. Confirm + clear destination ---------------------------------------------

if (Test-Path $InstallRoot) {
    if (-not $Force) {
        Write-Host ""
        Write-Host "$InstallRoot already exists." -ForegroundColor Yellow
        $reply = Read-Host "Overwrite? (y/N)"
        if ($reply -notmatch '^(y|Y)') {
            Write-Host "Cancelled. Existing install left untouched." -ForegroundColor Yellow
            exit 0
        }
    }
    Write-Step "Removing existing install at $InstallRoot"
    Remove-Item -Recurse -Force $InstallRoot
}

# 3. Copy the bundle ---------------------------------------------------------

Write-Step "Installing to $InstallRoot"
$parent = Split-Path -Parent $InstallRoot
if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent | Out-Null
}
Copy-Item -Recurse -Force -Path $BundleSrc -Destination $InstallRoot
$totalBytes = (Get-ChildItem -Recurse -File $InstallRoot | Measure-Object -Property Length -Sum).Sum
$totalGB = [math]::Round($totalBytes / 1GB, 2)
Write-Host "  Copied $totalGB GB."

# 4. Create Start Menu shortcut ----------------------------------------------

Write-Step "Creating Start Menu shortcut"
$startMenuParent = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startMenuDir = Join-Path $startMenuParent "InscriptionSuite"
if (-not (Test-Path $startMenuDir)) {
    New-Item -ItemType Directory -Path $startMenuDir | Out-Null
}
$startShortcut = Join-Path $startMenuDir "Inscription Suite.lnk"

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($startShortcut)
$lnk.TargetPath = "powershell.exe"
$lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$InstallRoot\start-suite.ps1`""
$lnk.WorkingDirectory = $InstallRoot
$lnk.Description = "Inscription Suite air-gapped launcher (Inscription / CaseForge / CaseGuide)"
$icon = Join-Path $InstallRoot "Inscription\Inscription.exe"
if (Test-Path $icon) {
    $lnk.IconLocation = "$icon,0"
}
$lnk.Save()
Write-Host "  $startShortcut"

# 5. Optional desktop shortcut -----------------------------------------------

if ($DesktopShortcut) {
    Write-Step "Creating Desktop shortcut"
    $desktop = [Environment]::GetFolderPath("Desktop")
    $desktopShortcut = Join-Path $desktop "Inscription Suite.lnk"
    Copy-Item -Force $startShortcut $desktopShortcut
    Write-Host "  $desktopShortcut"
}

# 6. Optional PowerShell 7 install -------------------------------------------

if ($InstallPowerShell7) {
    $msi = Get-ChildItem -Path $InstallRoot -Filter "PowerShell-*-win-x64.msi" -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($msi) {
        Write-Step "Installing PowerShell 7 from $($msi.Name)"
        # /qb gives a minimal progress UI rather than a fully silent
        # install; air-gapped admins generally want to see "this is
        # actually running" feedback.
        $proc = Start-Process -FilePath "msiexec.exe" `
            -ArgumentList "/i", "`"$($msi.FullName)`"", "/qb" `
            -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            Write-Host "  msiexec returned exit code $($proc.ExitCode); see %WINDIR%\Logs\WindowsUpdate or the Windows installer log." -ForegroundColor Yellow
        } else {
            Write-Host "  PowerShell 7 installed." -ForegroundColor Green
        }
    } else {
        Write-Host "No PowerShell 7 MSI found in the bundle -- skipping." -ForegroundColor Yellow
        Write-Host "  (Re-build with prepare-bundle.ps1 -IncludePowerShell7 if you want it bundled.)"
    }
}

# 7. Final report ------------------------------------------------------------

Write-Host ""
Write-Host "Inscription Suite installed." -ForegroundColor Green
Write-Host "  Location:       $InstallRoot"
Write-Host "  Start Menu:     Start -> InscriptionSuite -> 'Inscription Suite'"
if ($DesktopShortcut) {
    Write-Host "  Desktop icon:   'Inscription Suite' on your desktop"
}
Write-Host ""
Write-Host "First launch fires a UAC prompt -- start-suite.ps1 self-elevates so"
Write-Host "Inscription's UI-automation can read elevated forensic tools (AXIOM,"
Write-Host "X-Ways, etc.). Accept the prompt to continue."
