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

:: Try to activate virtual environment
if exist "%~dp0venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call "%~dp0venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call "venv\Scripts\activate.bat"
) else if exist "%~dp0.venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call ".venv\Scripts\activate.bat"
) else (
    echo [INFO] No virtual environment found. Creating one...
    python -m venv venv
    call "venv\Scripts\activate.bat"
    echo [INFO] Installing requirements...
    pip install -r requirements.txt
)

python gateway.py %*

pause
