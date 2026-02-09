@echo off
echo Starting B2B Platform with Ngrok Tunnel...
echo.

echo 1. Checking if B2B Launcher is running...
tasklist | findstr B2BLauncher > nul
if errorlevel 1 (
    echo Starting B2B Launcher...
    Start-Process -WindowStyle Hidden -FilePath "B2BLauncher.exe"
    echo Waiting 20 seconds for services to start...
    timeout /t 20 /nobreak
) else (
    echo B2B Launcher is already running!
)

echo.
echo 2. Starting Ngrok tunnel for frontend (port 3000)...
echo This will create a public URL like: https://xxxxx.ngrok.io
echo.

REM Check if ngrok exists, if not download it
if not exist "ngrok.exe" (
    echo Downloading ngrok...
    powershell -Command "Invoke-WebRequest -Uri 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip' -OutFile 'ngrok.zip'"
    powershell -Command "Expand-Archive -Path 'ngrok.zip' -DestinationPath '.'"
    del ngrok.zip
)

echo Starting ngrok...
.\ngrok.exe http 3000

pause
