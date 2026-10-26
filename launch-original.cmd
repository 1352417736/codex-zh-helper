@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 (
  start "" pyw -3 -m codex_zh_helper --launch-original
  exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw -m codex_zh_helper --launch-original
  exit /b
)
python -m codex_zh_helper --launch-original
if errorlevel 1 pause
