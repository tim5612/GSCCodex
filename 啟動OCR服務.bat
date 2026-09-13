@echo off
setlocal

title Product OCR and QR Code Server
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found:
    echo %~dp0.venv\Scripts\python.exe
    echo.
    echo Install Python 3.12 and the packages in requirements.txt first.
    pause
    exit /b 1
)

set "FOUND_SERVER=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":5000 .*LISTENING"') do (
    set "FOUND_SERVER=1"
    echo Stopping existing server on port 5000 ^(PID %%P^)...
    powershell -NoProfile -Command "Stop-Process -Id %%P -Force -ErrorAction SilentlyContinue"
)

if "%FOUND_SERVER%"=="1" (
    powershell -NoProfile -Command "Start-Sleep -Seconds 1"
    echo Existing server stopped.
    echo.
)

set "ENABLE_EASYOCR=1"

echo Starting Product OCR and QR Code Server...
echo Loading the OCR model may take about 20 seconds.
echo.

".venv\Scripts\python.exe" app.py

echo.
echo Server stopped.
pause
endlocal
