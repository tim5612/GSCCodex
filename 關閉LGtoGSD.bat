@echo off
setlocal
title Switch LGDevB to GSD
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Administrator permission is required.
    echo Run PowerShell as Administrator, then run this BAT again.
    echo.
    pause
    exit /b 1
)

set "CF_EXE="
for /f "delims=" %%I in ('where cloudflared.exe 2^>nul') do if not defined CF_EXE set "CF_EXE=%%I"
if not defined CF_EXE if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" set "CF_EXE=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if not defined CF_EXE if exist "C:\Program Files\cloudflared\cloudflared.exe" set "CF_EXE=C:\Program Files\cloudflared\cloudflared.exe"

if not defined CF_EXE (
    echo [ERROR] cloudflared.exe was not found.
    echo.
    pause
    exit /b 1
)

echo Checking the OCR service at http://127.0.0.1:5000 ...
powershell.exe -NoProfile -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5000' -TimeoutSec 3; if ($response.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if errorlevel 1 (
    echo OCR is not running. Starting it in a new window...
    start "GSD OCR Server" "%~dp0start_GSD_OCR.bat"
    echo OCR model loading may take about 20 seconds.
) else (
    echo OCR is already running.
)

echo.
echo ============================================================
echo Paste the GSD Tunnel token below, then press Enter.
echo The token will NOT be saved in this BAT file.
echo ============================================================
set "GSD_TOKEN="
set /p "GSD_TOKEN=GSD Token: "

if not defined GSD_TOKEN (
    echo.
    echo [ERROR] No token was entered. LGDevB was not stopped.
    pause
    exit /b 1
)

echo.
echo Token received. Stopping the LGDevB Cloudflared service...
powershell.exe -NoProfile -Command "Stop-Service -Name Cloudflared -ErrorAction Stop"
if errorlevel 1 (
    set "GSD_TOKEN="
    echo [ERROR] Could not stop the Cloudflared service.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting the GSD Tunnel...
echo Keep this window open while using GSD.
echo To switch back, run the GSD-to-LG BAT file as Administrator.
echo.
"%CF_EXE%" tunnel run --token "%GSD_TOKEN%"

set "GSD_TOKEN="
echo.
echo The GSD Tunnel has stopped. Restoring LGDevB...
powershell.exe -NoProfile -Command "Start-Service -Name Cloudflared -ErrorAction SilentlyContinue"
echo The LGDevB start command has been sent.
pause
endlocal
