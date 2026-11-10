@echo off
setlocal EnableExtensions
TITLE NWIS-Sentinel ^| Single-Port Gateway Launcher
REM One-click launcher (cmd): sets up .venv (Python 3.11/3.10) on first run,
REM installs requirements.txt when it changes, then starts the gateway on :5000.
REM Extra arguments are passed to gateway.py, e.g.  start_all.bat --no-browser

echo =========================================================================
echo    NWIS-Sentinel -- Oil India Limited -- SIH 2026 (PS SIH26121)
echo    Starting Single-Port Gateway  -^>  http://localhost:5000
echo =========================================================================
echo.

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "REQ=%ROOT%requirements.txt"
set "STAMP=%VENV%\requirements.installed"
set "VERCHK=import sys; sys.exit(0 if sys.version_info[:2] in ((3,10),(3,11)) else 1)"

REM 1. Existing venv must be Python 3.10/3.11 (PaddleOCR has no build for newer Pythons)
if exist "%VPY%" (
    "%VPY%" -c "%VERCHK%" >nul 2>nul || (
        echo [INFO] .venv uses an unsupported Python version - recreating it.
        rmdir /s /q "%VENV%"
    )
)

REM 2. Create the venv if needed
if not exist "%VPY%" (
    set "BASEPY="
    py -3.11 -c "%VERCHK%" >nul 2>nul && set "BASEPY=py -3.11"
    if not defined BASEPY py -3.10 -c "%VERCHK%" >nul 2>nul && set "BASEPY=py -3.10"
    if not defined BASEPY python -c "%VERCHK%" >nul 2>nul && set "BASEPY=python"
    call :createvenv
    if errorlevel 1 exit /b 1
)

REM 3. Install / update dependencies only when requirements.txt changed
set "NEEDINSTALL=1"
if exist "%STAMP%" fc /b "%REQ%" "%STAMP%" >nul 2>nul && set "NEEDINSTALL=0"
if "%NEEDINSTALL%"=="1" (
    echo [INFO] Installing requirements ^(first run downloads ~2-3 GB, takes several minutes^)...
    "%VPY%" -m pip install --upgrade pip --quiet
    "%VPY%" -m pip install -r "%REQ%"
    if errorlevel 1 (
        echo [ERROR] pip install failed - see messages above.
        pause
        exit /b 1
    )
    copy /y "%REQ%" "%STAMP%" >nul
) else (
    echo [INFO] Dependencies up to date.
)

REM 4. Start the gateway (it launches every module with this same interpreter)
cd /d "%ROOT%NLP\nlp_task_ddr"
"%VPY%" gateway.py %*
pause
exit /b 0

:createvenv
if not defined BASEPY (
    echo [ERROR] Python 3.11 ^(or 3.10^) not found. Install it from https://www.python.org/downloads/ and re-run.
    pause
    exit /b 1
)
echo [INFO] Creating virtual environment ^(.venv^) with: %BASEPY%
%BASEPY% -m venv "%VENV%"
exit /b %errorlevel%
