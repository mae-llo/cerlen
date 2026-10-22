@echo off
rem Starts Cerlen on Windows. Run setup first (see README.md).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run the setup steps in README.md first.
  exit /b 1
)
.venv\Scripts\python.exe -m cerlen
