@echo off
title PaviScan
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo O ambiente ainda nao foi instalado. De dois cliques em Instalar.bat primeiro.
  pause
  exit /b 1
)
echo.
echo   PaviScan abrindo em http://localhost:8501
echo   Para encerrar, feche esta janela.
echo.
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8501"
".venv\Scripts\python.exe" -m streamlit run src\paviscan\painel\app.py --server.port 8501 --server.headless true
echo.
echo O PaviScan parou. Se a porta 8501 ja estava em uso, feche a outra janela do PaviScan.
pause
