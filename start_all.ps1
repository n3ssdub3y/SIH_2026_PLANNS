# NWIS-Sentinel | SIH 2026 | PS SIH26121
# One-click launcher (PowerShell): sets up .venv (Python 3.11/3.10) on first run,
# installs requirements.txt when it changes, then starts the gateway on :5000.
# Usage:  .\start_all.ps1            (extra args are passed to gateway.py, e.g. --no-browser)

$ErrorActionPreference = "Stop"
$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv    = Join-Path $Root ".venv"
$VenvPy  = Join-Path $Venv "Scripts\python.exe"
$Req     = Join-Path $Root "requirements.txt"
$Stamp   = Join-Path $Venv "requirements.installed"

Write-Host "`n=========================================================================" -ForegroundColor Cyan
Write-Host "   NWIS-Sentinel -- Oil India Limited -- SIH 2026 (PS SIH26121)" -ForegroundColor Cyan
Write-Host "   Single-Port Gateway  ->  http://localhost:5000" -ForegroundColor Cyan
Write-Host "=========================================================================`n" -ForegroundColor Cyan

function Test-PyVersion($exe, $prefix) {
    try {
        $v = & $exe @prefix -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
        return ($v -eq "3.11" -or $v -eq "3.10")
    } catch { return $false }
}

# 1. Existing venv must be Python 3.10/3.11 (PaddleOCR has no build for newer Pythons)
if ((Test-Path $VenvPy) -and -not (Test-PyVersion $VenvPy @())) {
    Write-Host "[INFO] .venv uses an unsupported Python version - recreating it." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $Venv
}

# 2. Create the venv if needed
if (-not (Test-Path $VenvPy)) {
    $base = $null
    foreach ($cand in @(@("py", "-3.11"), @("py", "-3.10"), @("python"), @("python3"))) {
        $exe = $cand[0]; $pre = @($cand | Select-Object -Skip 1)
        if ((Get-Command $exe -ErrorAction SilentlyContinue) -and (Test-PyVersion $exe $pre)) { $base = $cand; break }
    }
    if (-not $base) {
        Write-Host "[ERROR] Python 3.11 (or 3.10) not found. Install it from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    Write-Host "[INFO] Creating virtual environment (.venv) with: $($base -join ' ')" -ForegroundColor Cyan
    $exe = $base[0]; $pre = @($base | Select-Object -Skip 1)
    & $exe @pre -m venv $Venv
}

# 3. Install / update dependencies only when requirements.txt changed
$needInstall = -not (Test-Path $Stamp)
if (-not $needInstall) {
    $needInstall = (Get-FileHash $Req).Hash -ne (Get-FileHash $Stamp).Hash
}
if ($needInstall) {
    Write-Host "[INFO] Installing requirements (first run downloads ~2-3 GB, takes several minutes)..." -ForegroundColor Cyan
    & $VenvPy -m pip install --upgrade pip --quiet
    & $VenvPy -m pip install -r $Req
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] pip install failed - see messages above." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    Copy-Item $Req $Stamp -Force
} else {
    Write-Host "[INFO] Dependencies up to date." -ForegroundColor Green
}

# 4. Start the gateway (it launches every module with this same interpreter)
Set-Location (Join-Path $Root "NLP\nlp_task_ddr")
& $VenvPy gateway.py @args

Write-Host "Press any key to continue..."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
