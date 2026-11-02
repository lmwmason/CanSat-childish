@echo off
rem Launcher for the KAIST CanSat ground station on Windows. The first run installs what it needs.
setlocal
set "HERE=%~dp0"
set "ROOT=%HERE%.."
cd /d "%ROOT%"
if not exist "%HERE%.venv\Scripts\python.exe" (
  echo First run: creating a Python environment and installing packages ...
  py -3 -m venv "%HERE%.venv" || python -m venv "%HERE%.venv" || (echo Python 3 was not found. Install it from python.org and run this again. & pause & exit /b 1)
  "%HERE%.venv\Scripts\python.exe" -m pip install -q -r "%HERE%requirements.txt" || (echo Package install failed. & pause & exit /b 1)
)
if "%~1"=="" (
  "%HERE%.venv\Scripts\python.exe" -m kaist_ground_station --demo
) else (
  "%HERE%.venv\Scripts\python.exe" -m kaist_ground_station %*
)
