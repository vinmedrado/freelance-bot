@echo off
REM Inicia o watchdog do dashboard Flask do freelance_bot.

cd /d "%~dp0"

start "FreelanceBot Watchdog" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dashboard_forever.ps1" -OpenBrowser

timeout /t 6 /nobreak >nul
start "" "http://localhost:5050"
