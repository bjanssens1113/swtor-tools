@echo off
rem Same as SWTOR Overlay.bat but keeps a console open so errors are visible. Use this if the overlay won't start.
cd /d "%~dp0"
".venv\Scripts\python.exe" "overlay\main.py" --settings
pause
