@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python eval\make_release.py
echo.
echo Upload the contents of the release\weedguard folder to the new GitHub repository.
pause
