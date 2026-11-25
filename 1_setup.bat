@echo off
cd /d "%~dp0"
echo ============================================
echo   WeedGuard setup (step 1 of 3)
echo ============================================
where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer from python.org ^(tick "Add to PATH"^), then run this again.
  pause & exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
  echo Node.js was not found. Install the LTS version from nodejs.org, then run this again.
  pause & exit /b 1
)
python --version
node --version
if not exist .venv (
  echo Creating Python environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
echo Installing Python packages...
set TRIES=0
:pipretry
set /a TRIES+=1
pip install -q --retries 10 --timeout 60 -r weedguard\requirements.txt -r eval\requirements.txt
if not errorlevel 1 goto pipdone
if %TRIES% LSS 5 (
  echo Internet connection dropped. Trying again ^(attempt %TRIES% of 5^)...
  timeout /t 10 >nul
  goto pipretry
)
echo Package install failed 5 times. Check your internet connection and run 1_setup.bat again.
pause & exit /b 1
:pipdone
if exist tools\node_modules\@2ndbrainlabs-ai\synapse-cli\dist\index.js goto synapseok
echo Installing the Synapse CLI into the tools folder...
call npm install --prefix tools --ignore-scripts --fetch-retries=5 --no-audit --no-fund @2ndbrainlabs-ai/synapse-cli
if not exist tools\node_modules\@2ndbrainlabs-ai\synapse-cli\dist\index.js ( echo Synapse install failed. Check your internet connection and run 1_setup.bat again. & pause & exit /b 1 )
:synapseok
echo Synapse CLI is installed.
echo.
if not exist synapse_key.txt goto asksyn
for %%A in (synapse_key.txt) do if %%~zA LSS 10 goto asksyn
goto llm
:asksyn
set /p SKEY=Paste your SYNAPSE API key and press Enter: 
> synapse_key.txt echo %SKEY%
:llm
if not exist llm_key.txt goto askllm
for %%A in (llm_key.txt) do if %%~zA LSS 10 goto askllm
goto checkkey
:askllm
set /p LKEY=Paste your GROQ API key (starts with gsk_) and press Enter: 
> llm_key.txt echo %LKEY%
:checkkey
set /p LLM_API_KEY=<llm_key.txt
echo Checking the Groq key...
python eval\check_key.py
if errorlevel 1 ( echo. & echo Key check failed. To enter a new key, delete llm_key.txt and run this again. & pause & exit /b 1 )
echo.
echo Setup finished. Now double-click 2_build_with_synapse.bat
pause
