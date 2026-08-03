@echo off
REM Inicia o dashboard Flask do freelance_bot.
REM Coloque este arquivo na pasta de Inicialização do Windows para que o painel seja iniciado automaticamente ao ligar o notebook.

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if exist ".venv\Scripts\python.exe" (
  set PYTHON="%~dp0.venv\Scripts\python.exe"
) else (
  set PYTHON="%~dp0venv\Scripts\python.exe"
)

start "Freelance Radar" %PYTHON% webapp.py

timeout /t 6 /nobreak >nul
start "" "http://localhost:5050"
