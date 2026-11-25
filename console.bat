@echo off
title WeedGuard operator console (robot screen)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python weedguard\console.py
pause
