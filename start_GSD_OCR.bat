@echo off
setlocal
title GSD OCR Server
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found:
    echo %~dp0.venv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

set "ENABLE_EASYOCR=1"
echo Starting the GSD OCR Server on port 5000...
echo Loading the OCR model may take about 20 seconds.
echo.

".venv\Scripts\python.exe" app.py

echo.
echo The GSD OCR Server has stopped.
pause
endlocal
