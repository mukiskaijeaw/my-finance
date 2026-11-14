@echo off
cd /d "%~dp0"
python dashboard\server.py --open
if errorlevel 1 pause
