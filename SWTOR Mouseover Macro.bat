@echo off
rem Starts the AutoHotkey v2 mouseover macro (separate process from the overlay, on purpose).
cd /d "%~dp0"
start "" "%LOCALAPPDATA%\Programs\AutoHotkey\v2\AutoHotkey64.exe" "macro\mouseover.ahk"
