@echo off
setlocal
title Switch GSD to LGDevB

fltmc >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Administrator permission is required.
    echo Run PowerShell as Administrator, then run this BAT again.
    echo.
    pause
    exit /b 1
)

echo Stopping the GSD Tunnel...
powershell.exe -NoProfile -Command "Stop-Service -Name Cloudflared -Force -ErrorAction SilentlyContinue"
taskkill /F /IM cloudflared.exe >nul 2>&1

echo Starting the LGDevB Cloudflared service...
powershell.exe -NoProfile -Command "Start-Service -Name Cloudflared -ErrorAction Stop"
if errorlevel 1 (
    echo [ERROR] The LGDevB Cloudflared service could not be started.
    echo.
    pause
    exit /b 1
)

echo.
powershell.exe -NoProfile -Command "Get-Service -Name Cloudflared | Format-Table Status,Name,DisplayName -AutoSize"
echo LGDevB has been restored.
echo Cloudflare may take 10 to 30 seconds to show Healthy.
echo.
pause
endlocal
