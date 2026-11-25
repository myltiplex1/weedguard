@echo off
cd /d "%~dp0"
echo ============================================
echo   Build the weed_plot tool with Synapse (step 2 of 3)
echo ============================================
call .venv\Scripts\activate.bat
if exist synapse_key.txt set /p SYNAPSE_API_KEY=<synapse_key.txt
if exist llm_key.txt set /p LLM_API_KEY=<llm_key.txt
set PYTHONIOENCODING=utf-8
python eval\synapse_build.py %*
if errorlevel 1 (
  echo.
  echo Something did not pass. Details are in the "results" folder.
  pause & exit /b 1
)
echo.
echo Build and safety checks passed. Next: run 3_run_comparison.bat
pause
