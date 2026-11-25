@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set /p LLM_API_KEY=<llm_key.txt
set PYTHONIOENCODING=utf-8
python eval\chat.py %*
pause
