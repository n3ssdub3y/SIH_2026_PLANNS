@echo off
TITLE NWIS-Sentinel | Single-Port Gateway Launcher
cd /d "%~dp0NLP\nlp_task_ddr"
python gateway.py %*
pause
