@echo off
echo Starting Cloudflare Tunnel for B2B Platform...
echo.

echo 1. Starting B2B Launcher...
start /B B2BLauncher.exe

echo 2. Waiting 10 seconds for services to start...
timeout /t 10 /nobreak

echo 3. Starting Cloudflare Tunnel...
Start-Process -WindowStyle Hidden -FilePath ".\cloudflared.exe" -ArgumentList "tunnel","--config","cloudflared.yml","run","b2b-platform"

echo.
echo Tunnel is running! Your site is available at:
echo - Frontend: https://b2b-platform.trycloudflare.com
echo - API: https://api-b2b-platform.trycloudflare.com  
echo - Parser: https://parser-b2b-platform.trycloudflare.com
echo.
echo Press any key to stop...
pause > nul

echo Stopping tunnel...
taskkill /F /IM cloudflared.exe
echo Tunnel stopped.
