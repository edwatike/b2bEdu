@echo off
setlocal
chcp 65001 >nul
set ROOT=D:\b2b
if not exist %ROOT%\TEMP mkdir %ROOT%\TEMP

REM Ensure localhost does NOT go through corporate/system proxy (avoids false 503)
set NO_PROXY=localhost,127.0.0.1
set no_proxy=localhost,127.0.0.1
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=

echo [0/4] Comet CDP (9222)...

set "COMET_PROFILE="
if exist "D:\tryagain\TEMP\comet-profile" set "COMET_PROFILE=D:\tryagain\TEMP\comet-profile"
if not defined COMET_PROFILE set "COMET_PROFILE=%ROOT%\TEMP\comet-profile"
if not exist "%COMET_PROFILE%" mkdir "%COMET_PROFILE%"

set "COMET_EXE="
for %%P in (
  "%LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe"
  "%USERPROFILE%\AppData\Local\Perplexity\Comet\Application\comet.exe"
  "C:\Program Files\Perplexity\Comet\Application\comet.exe"
  "C:\Program Files (x86)\Perplexity\Comet\Application\comet.exe"
) do (
  if exist "%%~fP" set "COMET_EXE=%%~fP"
)

set "CDP_ALREADY_LISTENING="
for /f "usebackq delims=" %%L in (`powershell -NoProfile -NonInteractive -Command "if (Get-NetTCPConnection -State Listen -LocalPort 9222 -ErrorAction SilentlyContinue) { 'YES' }"`) do set "CDP_ALREADY_LISTENING=%%L"

if /I "%CDP_ALREADY_LISTENING%"=="YES" (
  echo Comet CDP already listening on :9222
) else (
  tasklist /FI "IMAGENAME eq comet.exe" 2>NUL | find /I "comet.exe" >NUL
  if %ERRORLEVEL%==0 (
    if /I "%AUTO_KILL_BROWSER_FOR_CDP%"=="1" (
      echo Comet is running. Closing it to enable CDP :9222...
      taskkill /IM comet.exe /T /F >NUL 2>&1
    ) else (
      echo WARNING: Comet is already running. Close Comet and re-run RunB2B.bat to enable CDP :9222.
      echo Hint: set AUTO_KILL_BROWSER_FOR_CDP=1 to auto-close Comet from this script.
    )
  )

  if defined COMET_EXE (
    start "" "%COMET_EXE%" --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="%COMET_PROFILE%" "http://localhost:3000/login"
  ) else (
    echo WARNING: Perplexity Comet not found. Install Comet or provide comet.exe path.
  )
)

echo [1/4] Parser (9004)...
cd /d %ROOT%\parser_service
if not exist venv python -m venv venv
venv\Scripts\pip.exe install --progress-bar on --disable-pip-version-check -r requirements.txt
start "" "%ROOT%\parser_service\venv\Scripts\python.exe" "%ROOT%\parser_service\run_api.py"

echo [2/4] Backend (8000)...
cd /d %ROOT%\backend
if not exist venv python -m venv venv
venv\Scripts\pip.exe install --progress-bar on --disable-pip-version-check -r requirements.txt
start "" "%ROOT%\backend\venv\Scripts\python.exe" "%ROOT%\backend\run_api.py"

echo [3/4] Frontend (3000)...
cd /d %ROOT%\frontend\moderator-dashboard-ui
set NEXT_TELEMETRY_DISABLED=1
set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
if not exist node_modules npm install --no-audit --progress=true
start "" cmd.exe /c "npm run dev"

echo URLs:
echo - Parser: http://127.0.0.1:9004/health
echo - Backend: http://127.0.0.1:8000/health
echo - Frontend: http://localhost:3000/login
