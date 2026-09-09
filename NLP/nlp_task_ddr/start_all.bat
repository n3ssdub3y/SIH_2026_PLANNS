@echo off
TITLE NWIS-Sentinel | System Launcher
echo =========================================================================
echo    NWIS-Sentinel -- Oil India Limited -- SIH 2026 (PS SIH26121)
echo    Starting all 4 Modules Simultaneously (Ports 5001, 5002, 5003, 5004)
echo =========================================================================
echo.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH! Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

python run_all_modules.py %*

pause
