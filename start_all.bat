@echo off
TITLE NWIS-Sentinel | Single-Port Gateway Launcher
echo =========================================================================
echo    NWIS-Sentinel -- Oil India Limited -- SIH 2026 (PS SIH26121)
echo    Starting Single-Port Gateway  -^>  http://localhost:5000
echo =========================================================================
echo.

cd /d "%~dp0NLP\nlp_task_ddr"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

python gateway.py %*

pause
