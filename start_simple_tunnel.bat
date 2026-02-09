@echo off
echo Starting B2B Platform with Cloudflare Tunnel...
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
echo 2. Starting Cloudflare Tunnel for frontend (port 3000)...
echo This will create a temporary URL like: https://xxxxx.trycloudflare.com
echo.
.\cloudflared.exe tunnel --url http://localhost:3000
