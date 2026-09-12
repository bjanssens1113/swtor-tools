@echo off
rem Starts the SWTOR combat-log overlay (tray app). Self-contained: uses the Python in this folder.
rem Double-clicking again while it runs does nothing (single instance).
cd /d "%~dp0"
if not exist "python\pythonw.exe" (
  echo python\pythonw.exe is missing. Re-run overlay\tools\setup_python.cmd  ^(or see README^).
  pause
  exit /b 1
)
start "" "python\pythonw.exe" "overlay\main.py"
