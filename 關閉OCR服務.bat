@echo off
setlocal

title Stop Product OCR and QR Code Server
cd /d "%~dp0"

set "FOUND_SERVER=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":5000 .*LISTENING"') do (
    set "FOUND_SERVER=1"
    echo Stopping server on port 5000 ^(PID %%P^)...
    powershell -NoProfile -Command "Stop-Process -Id %%P -Force -ErrorAction SilentlyContinue"
)

if "%FOUND_SERVER%"=="0" (
    echo No OCR server is currently listening on port 5000.
) else (
    powershell -NoProfile -Command "Start-Sleep -Seconds 1"
    echo OCR server stopped.
)

echo.
pause
endlocal
