@echo off
echo Starting B2B Platform with Multiple Cloudflare Tunnels...
echo.

echo 1. Checking if B2B Launcher is running...
tasklist | findstr B2BLauncher > nul
if errorlevel 1 (
    echo Starting B2B Launcher...
    start /B B2BLauncher.exe
    echo Waiting 15 seconds for services to start...
    timeout /t 15 /nobreak
) else (
    echo B2B Launcher is already running!
)

echo.
echo 2. Starting Cloudflare Tunnels...
echo.

echo Starting tunnel for Frontend (port 3000)...
start "Frontend Tunnel" cmd /k ".\cloudflared.exe tunnel --url http://localhost:3000"

echo Starting tunnel for Backend API (port 8000)...
start "Backend Tunnel" cmd /k ".\cloudflared.exe tunnel --url http://localhost:8000"

echo Starting tunnel for Parser Service (port 9000)...
start "Parser Tunnel" cmd /k ".\cloudflared.exe tunnel --url http://localhost:9000"

echo.
echo All tunnels are starting in separate windows...
echo Each tunnel will show its unique trycloudflare.com URL
echo.
echo Press any key to stop all tunnels...
pause > nul

echo Stopping all tunnels...
taskkill /F /IM cloudflared.exe
echo All tunnels stopped.
