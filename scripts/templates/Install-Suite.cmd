@echo off
REM ============================================================
REM   Install the Inscription Suite to this workstation.
REM
REM   Double-click this file inside the unzipped bundle folder.
REM   It runs install.ps1 for you with the ExecutionPolicy
REM   bypass needed on a workstation that's never seen our
REM   scripts before -- saves you the right-click "Run with
REM   PowerShell" dance and the Set-ExecutionPolicy step.
REM
REM   Pass any install.ps1 arguments through unchanged, e.g.:
REM       Install-Suite.cmd -DesktopShortcut
REM       Install-Suite.cmd -InstallPowerShell7
REM       Install-Suite.cmd -Force
REM ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
    echo.
    echo Install reported an error -- see above for details.
    echo Press any key to close...
    pause >nul
)
