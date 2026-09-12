@echo off
rem Rebuilds the self-contained Python in <repo>\python from scratch (needs uv: https://docs.astral.sh/uv/).
rem Run this if python\ is missing or broken.
cd /d "%~dp0..\.."
set UV=%USERPROFILE%\.local\bin\uv.exe
if not exist "%UV%" set UV=uv
"%UV%" python install 3.13 || exit /b 1
for /f "delims=" %%p in ('"%UV%" python find 3.13') do set BASE=%%~dpp
if exist python rmdir /s /q python
robocopy "%BASE%." python /E /NFL /NDL /NJH /NJS /NP >nul
del /q python\Lib\EXTERNALLY-MANAGED 2>nul
python\python.exe -m pip install --upgrade PyQt6 pywin32 pytest || exit /b 1
python\python.exe -c "import PyQt6.QtWidgets, win32com.client; print('python\ ready')"
