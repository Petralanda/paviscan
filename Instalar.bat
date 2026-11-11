@echo off
title PaviScan - instalacao
cd /d "%~dp0"
echo Instalando o PaviScan (leva de 5 a 10 minutos na primeira vez)...
py -3.12 -m venv .venv 2>nul || python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo Nao achei o Python. Instale o Python 3.12 em python.org e rode de novo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
echo.
echo Pronto. Agora de dois cliques em PaviScan.bat.
pause
