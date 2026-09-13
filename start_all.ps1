# NWIS-Sentinel | SIH 2026 | PS SIH26121
# PowerShell master launcher (Single-Port Gateway)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ScriptDir\NLP\nlp_task_ddr"
python gateway.py @args
