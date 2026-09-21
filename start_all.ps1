# NWIS-Sentinel | SIH 2026 | PS SIH26121
# PowerShell launcher — Single-Port Gateway

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ScriptDir\NLP\nlp_task_ddr"

Write-Host "`n=========================================================================" -ForegroundColor Cyan
Write-Host "   NWIS-Sentinel -- Oil India Limited -- SIH 2026 (PS SIH26121)" -ForegroundColor Cyan
Write-Host "   Single-Port Gateway  ->  http://localhost:5000" -ForegroundColor Cyan
Write-Host "=========================================================================`n" -ForegroundColor Cyan

python gateway.py $args
