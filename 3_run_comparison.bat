@echo off
cd /d "%~dp0"
echo ============================================
echo   One tool vs many tools comparison (step 3 of 3)
echo   Runs every task with each free Groq model. Leave the laptop on.
echo   When a model reaches its free daily limit it moves on to the next one.
echo   Run this again the next day to finish: it continues where it stopped.
echo ============================================
call .venv\Scripts\activate.bat
set /p LLM_API_KEY=<llm_key.txt
set PYTHONIOENCODING=utf-8
python eval\run_eval.py --reps 1 %*
python eval\analyze.py > nul
echo.
echo Results: docs\RESULTS.md and docs\comparison.svg (raw runs in results\comparison)
pause
