@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai dat. Dang chay install.bat ...
  call install.bat
)
".venv\Scripts\python.exe" app.py
pause
