@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
set "LAUNCHER=%PROJECT_ROOT%scripts\run_real_model_launcher.py"

if not exist "%PYTHON_EXE%" (
  echo ERROR: Repository-local Python was not found:
  echo   "%PYTHON_EXE%"
  echo Create .venv and install the project before running Real evaluation.
  if /I not "%STAIRKID_NO_PAUSE%"=="1" pause
  exit /b 2
)

if not exist "%LAUNCHER%" (
  echo ERROR: Real model launcher was not found:
  echo   "%LAUNCHER%"
  if /I not "%STAIRKID_NO_PAUSE%"=="1" pause
  exit /b 3
)

pushd "%PROJECT_ROOT%" || exit /b 4
"%PYTHON_EXE%" "%LAUNCHER%"
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
  echo Real model test exited with code %EXIT_CODE%.
)
if /I not "%STAIRKID_NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
