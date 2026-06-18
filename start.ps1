# start.ps1 — Windows PowerShell launcher for Nous Switcher.
#
# Creates/uses a local .venv because Hermes' bundled Python environment layout
# can vary by platform. Keeps the server bound to 127.0.0.1 via server.py.

$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    $PythonCmd = "py"
    $PythonArgs = @("-3")
} else {
    $Python = Get-Command python -ErrorAction Stop
    $PythonCmd = "python"
    $PythonArgs = @()
}

if (-not (Test-Path ".venv")) {
    & $PythonCmd @PythonArgs -m venv .venv
}

$VenvPython = Join-Path $Here ".venv\Scripts\python.exe"
& $VenvPython -m pip install -r requirements.txt

Write-Host "nous_switcher -> http://127.0.0.1:9120"
Write-Host "  directory: $Here"
Write-Host "  Python   : $VenvPython"
Write-Host ""

& $VenvPython server.py
