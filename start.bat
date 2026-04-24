@echo off
title Wakilna - WhatsApp Bot Launcher
color 0A

echo ==========================================
echo        Wakilna WhatsApp Bot Launcher
echo ==========================================
echo.

:: Step 1 - Kill anything on port 3000
echo [1/3] Freeing port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo Done.

:: Step 2 - Start Python server in new window
echo [2/3] Starting Python server (FastAPI)...
start "Python Server" cmd /k "cd /d "%~dp0" && python -m uvicorn main:app --reload"
timeout /t 3 /nobreak >nul

:: Step 3 - Start Node server in new window
echo [3/3] Starting Node server...
start "Node Server" cmd /k "cd /d "%~dp0" && node index.js"
timeout /t 4 /nobreak >nul

:: Open dashboard in browser — served over HTTP, not file://
echo.
echo Opening Wakilna dashboard in browser...
start "" "http://localhost:3000"

echo.
echo ==========================================
echo  Both servers running!
echo  Dashboard: http://localhost:3000
echo  Scan QR in the browser tab that opened.
echo ==========================================
echo.
pause
