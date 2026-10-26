@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 (
  start "" pyw -3 -m codex_zh_helper
  exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw -m codex_zh_helper
  exit /b
)
python -m codex_zh_helper
if errorlevel 1 pause
