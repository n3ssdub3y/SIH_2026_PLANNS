@echo off
TITLE NWIS-Sentinel | System Launcher
cd /d "%~dp0\NLP\nlp_task_ddr"
python run_all_modules.py %*
pause
