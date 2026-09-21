# NWIS-Sentinel | SIH 2026 | PS SIH26121
# PowerShell launcher — Single-Port Gateway

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ScriptDir\NLP\nlp_task_ddr"

Write-Host "`n=========================================================================" -ForegroundColor Cyan
Write-Host "   NWIS-Sentinel -- Oil India Limited -- SIH 2026 (PS SIH26121)" -ForegroundColor Cyan
Write-Host "   Single-Port Gateway  ->  http://localhost:5000" -ForegroundColor Cyan
Write-Host "=========================================================================`n" -ForegroundColor Cyan

# Try to activate virtual environment
if (Test-Path "$ScriptDir\venv\Scripts\Activate.ps1") {
    Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Cyan
    & "$ScriptDir\venv\Scripts\Activate.ps1"
} elseif (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Cyan
    & ".\venv\Scripts\Activate.ps1"
} elseif (Test-Path "$ScriptDir\.venv\Scripts\Activate.ps1") {
    Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Cyan
    & "$ScriptDir\.venv\Scripts\Activate.ps1"
} elseif (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Cyan
    & ".\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "[INFO] No virtual environment found. Creating one..." -ForegroundColor Cyan
    python -m venv venv
    & ".\venv\Scripts\Activate.ps1"
    Write-Host "[INFO] Installing requirements..." -ForegroundColor Cyan
    pip install -r requirements.txt
}

python gateway.py $args

Write-Host "Press any key to continue..."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
