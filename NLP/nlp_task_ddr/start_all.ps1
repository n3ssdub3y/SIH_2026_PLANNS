# NWIS-Sentinel | SIH 2026 | PS SIH26121
# PowerShell launcher for all 4 modules simultaneously

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "`n=========================================================================" -ForegroundColor Cyan
Write-Host "   NWIS-Sentinel -- Oil India Limited -- SIH 2026 (PS SIH26121)" -ForegroundColor Cyan
Write-Host "   Starting all 4 Modules Simultaneously (Ports 5001, 5002, 5003, 5004)" -ForegroundColor Cyan
Write-Host "=========================================================================`n" -ForegroundColor Cyan

python run_all_modules.py $args
