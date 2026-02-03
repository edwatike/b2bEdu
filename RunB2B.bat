@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title RunB2B - Universal Launcher

REM ============================================
REM UNIVERSAL LAUNCHER - Works from ANY folder/worktree
REM Uses CD to determine project root
REM ============================================

set "PROJECT_ROOT=%CD%"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo.
echo ========================================
echo   B2B PLATFORM - UNIVERSAL LAUNCHER
echo ========================================
echo   Project: %PROJECT_ROOT%
echo ========================================
echo.

REM Verify required directories exist
if not exist "%PROJECT_ROOT%\parser_service" (
    echo ERROR: parser_service not found!
    exit /b 1
)
if not exist "%PROJECT_ROOT%\backend" (
    echo ERROR: backend not found!
    exit /b 1
)
if not exist "%PROJECT_ROOT%\frontend\moderator-dashboard-ui" (
    echo ERROR: frontend not found!
    exit /b 1
)

if not exist "%PROJECT_ROOT%\TEMP" mkdir "%PROJECT_ROOT%\TEMP" >nul 2>&1

REM ============================================
REM 0. Cleanup (FAST - no hangs)
REM ============================================
echo [0/4] Cleanup...
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force; Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1
timeout /t 2 /nobreak >nul
echo       Done
echo.

REM ============================================
REM 1. Parser Service (Port 9004)
REM ============================================
echo [1/4] Parser Service on port 9004...

if not exist "%PROJECT_ROOT%\parser_service\venv\Scripts\python.exe" (
    echo       Creating venv...
    cd /d "%PROJECT_ROOT%\parser_service"
    python -m venv venv --clear
    timeout /t 3 /nobreak >nul
    
    REM Check if venv created successfully
    if not exist "venv\Scripts\python.exe" (
        echo       ERROR: Failed to create venv
        goto :SKIP_PARSER
    )
    
    echo       Installing deps...
    "venv\Scripts\pip.exe" install -r requirements.txt > "%PROJECT_ROOT%\TEMP\parser_pip.log" 2>&1
)

cd /d "%PROJECT_ROOT%\parser_service"
start "Parser-9004" /MIN "venv\Scripts\python.exe" run_api.py
timeout /t 8 /nobreak >nul

curl -s --max-time 2 http://127.0.0.1:9004/health >nul 2>&1
if !errorlevel!==0 (
    echo       Running
) else (
    echo       Starting...
)
:SKIP_PARSER
echo.

REM ============================================
REM 2. Backend (Port 8010)
REM ============================================
echo [2/4] Backend on port 8010...

if not exist "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" (
    echo       Creating venv...
    cd /d "%PROJECT_ROOT%\backend"
    python -m venv venv --clear
    timeout /t 3 /nobreak >nul
    
    if not exist "venv\Scripts\python.exe" (
        echo       ERROR: Failed to create venv
        goto :SKIP_BACKEND
    )
    
    echo       Installing deps...
    "venv\Scripts\pip.exe" install -r requirements.txt > "%PROJECT_ROOT%\TEMP\backend_pip.log" 2>&1
    
    REM Create .env if missing
    if not exist ".env" if exist ".env.example" (
        copy .env.example .env >nul
    )
)

cd /d "%PROJECT_ROOT%\backend"
start "Backend-8010" /MIN "venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8010
timeout /t 10 /nobreak >nul

curl -s --max-time 2 http://127.0.0.1:8010/health >nul 2>&1
if !errorlevel!==0 (
    echo       Running
) else (
    echo       Starting...
)
:SKIP_BACKEND
echo.

REM ============================================
REM 3. Frontend (Port 3000)
REM ============================================
echo [3/4] Frontend on port 3000...
cd /d "%PROJECT_ROOT%\frontend\moderator-dashboard-ui"

set "NODE_OPTIONS=--max-old-space-size=2048"
set "NEXT_TELEMETRY_DISABLED=1"
set "NEXT_PUBLIC_API_URL=http://127.0.0.1:8010"
set "NEXT_PUBLIC_PARSER_URL=http://127.0.0.1:9004"

if not exist "node_modules" (
    echo       npm install...
    call npm install --no-audit --progress=false > "%PROJECT_ROOT%\TEMP\npm.log" 2>&1
)

start "Frontend-3000" /MIN cmd /c "npm run dev ^> %PROJECT_ROOT%\TEMP\frontend.log 2^>^&1"

REM Wait for frontend
for /L %%i in (1,1,20) do (
    curl -s --max-time 2 http://127.0.0.1:3000/login >nul 2>&1
    if !errorlevel!==0 goto :FRONTEND_OK
    timeout /t 2 /nobreak >nul
)
:FRONTEND_OK

curl -s --max-time 2 http://127.0.0.1:3000/login >nul 2>&1
if !errorlevel!==0 (
    echo       Running
) else (
    echo       Check %PROJECT_ROOT%\TEMP\frontend.log
)
echo.

REM ============================================
REM 4. Health Check
REM ============================================
echo ========================================
echo   HEALTH CHECK
echo ========================================
echo.

set "RUNNING=0"

curl -s --max-time 2 http://127.0.0.1:9004/health >nul 2>&1
if !errorlevel!==0 (
    echo   OK Parser:  http://127.0.0.1:9004
    set /a RUNNING+=1
) else (
    echo   FAIL Parser:  http://127.0.0.1:9004
)

curl -s --max-time 2 http://127.0.0.1:8010/health >nul 2>&1
if !errorlevel!==0 (
    echo   OK Backend: http://127.0.0.1:8010
    set /a RUNNING+=1
) else (
    echo   FAIL Backend: http://127.0.0.1:8010
)

curl -s --max-time 2 http://127.0.0.1:3000/login >nul 2>&1
if !errorlevel!==0 (
    echo   OK Frontend: http://localhost:3000
    set /a RUNNING+=1
) else (
    echo   FAIL Frontend: http://localhost:3000
)

echo.
echo ========================================
if !RUNNING!==3 (
    echo   RESULT: 3/3 SERVICES RUNNING
) else (
    echo   RESULT: !RUNNING!/3 SERVICES
)
echo ========================================
echo.

if !RUNNING!==3 (
    echo   SUCCESS!
    echo.
    echo   Access:
    echo   - http://localhost:3000
    echo   - http://127.0.0.1:8010/docs
    exit /b 0
) else (
    echo   Check TEMP\*.log for errors
    exit /b 1
)
