@echo off
rem Starts the SWTOR combat-log overlay (tray app). Safe to double-click again: a second copy exits.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "overlay\main.py"
