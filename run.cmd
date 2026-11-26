@echo off
rem CommentKit - run from source. The first run creates .venv and installs the dependencies.
rem   run.cmd                    open the app window
rem   run.cmd doctor             check the setup
rem   run.cmd compose "topic"    write one story video
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"

if exist "%VENV%\Scripts\commentkit-gui.exe" goto run

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.10 or newer, then run this again:
  echo     winget install Python.Python.3.12
  exit /b 1
)
echo First run: creating the environment and installing dependencies...
if not exist "%VENV%\Scripts\python.exe" python -m venv "%VENV%" || exit /b 1
"%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install --quiet -e "%ROOT%." || exit /b 1

:run
if "%~1"=="" (
  start "" "%VENV%\Scripts\commentkit-gui.exe"
  exit /b 0
)
"%VENV%\Scripts\commentkit.exe" %*
exit /b %errorlevel%
