@echo off
REM Roda o pipeline do freelance_bot sem interface, pensado para o Task
REM Scheduler do Windows. Ajusta o encoding para evitar erro de caractere
REM especial (mesmo bug do Unicode que resolvemos no webapp.py).

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

"%~dp0venv\Scripts\python.exe" -u main.py >> "%~dp0scheduled_run.log" 2>&1
