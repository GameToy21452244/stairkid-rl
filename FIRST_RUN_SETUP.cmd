@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PROJECT_ROOT=%~dp0"
set "VENV_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"

echo ================================================================
echo StairKid RL - First Run Setup
echo This installs local dependencies and prepares local-only assets.
echo It never starts the Real game and never sends keyboard actions.
echo ================================================================

if exist "%VENV_PYTHON%" goto install

py -3.12 -c "import sys; assert (3,11) ^<= sys.version_info[:2] ^< (3,14)" >nul 2>nul
if not errorlevel 1 (
  py -3.12 -m venv "%PROJECT_ROOT%.venv"
  goto venv_created
)
py -3.13 -c "import sys; assert (3,11) ^<= sys.version_info[:2] ^< (3,14)" >nul 2>nul
if not errorlevel 1 (
  py -3.13 -m venv "%PROJECT_ROOT%.venv"
  goto venv_created
)
py -3.11 -c "import sys; assert (3,11) ^<= sys.version_info[:2] ^< (3,14)" >nul 2>nul
if not errorlevel 1 (
  py -3.11 -m venv "%PROJECT_ROOT%.venv"
  goto venv_created
)
echo ERROR: Python 3.11, 3.12, or 3.13 was not found by the Windows py launcher.
echo Install Python 3.12, then run this file again.
goto failed

:venv_created
if not exist "%VENV_PYTHON%" (
  echo ERROR: Failed to create repository-local .venv.
  goto failed
)

:install
pushd "%PROJECT_ROOT%" || goto failed
"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto install_failed
"%VENV_PYTHON%" -m pip install --no-build-isolation -e ".[rl]"
if errorlevel 1 goto install_failed
"%VENV_PYTHON%" -m stair_agent.real.setup --project-root . --initialize
if errorlevel 1 goto install_failed

echo.
echo Canonical model setup
if exist "%PROJECT_ROOT%models\cache\fresh_v3_seed17_524288.zip" if exist "%PROJECT_ROOT%models\cache\v3_5_r4_seed142_655360.zip" (
  "%VENV_PYTHON%" scripts\fetch_models.py --all
  if not errorlevel 1 goto models_ready
)
echo Enter a folder containing these two Release files:
echo   fresh_v3_seed17_524288.zip
echo   v3_5_r4_seed142_655360.zip
set "MODEL_SOURCE_DIR=%STAIRKID_MODEL_SOURCE_DIR%"
if not defined MODEL_SOURCE_DIR if exist "%USERPROFILE%\Downloads\fresh_v3_seed17_524288.zip" if exist "%USERPROFILE%\Downloads\v3_5_r4_seed142_655360.zip" set "MODEL_SOURCE_DIR=%USERPROFILE%\Downloads"
if not defined MODEL_SOURCE_DIR set /p "MODEL_SOURCE_DIR=MODEL SOURCE DIRECTORY (optional): "
if "%MODEL_SOURCE_DIR:~-1%"=="\" set "MODEL_SOURCE_DIR=%MODEL_SOURCE_DIR:~0,-1%"
if defined MODEL_SOURCE_DIR (
  "%VENV_PYTHON%" scripts\fetch_models.py --all --source-dir "%MODEL_SOURCE_DIR%"
) else (
  "%VENV_PYTHON%" scripts\fetch_models.py --all
)
if errorlevel 1 (
  echo.
  echo MODEL_SETUP_INCOMPLETE: Release assets are not publicly auto-downloadable.
  echo Download the two canonical model files from the project Release,
  echo then run FIRST_RUN_SETUP.cmd again and enter their folder.
  popd
  goto failed
)

:models_ready
"%VENV_PYTHON%" -m stair_agent.real.setup --project-root . --check
if errorlevel 1 (
  echo.
  echo DEPENDENCIES_AND_MODELS=PASS
  echo REAL_CALIBRATION=PENDING
  echo Next: double-click CALIBRATE_REAL_GAME.cmd once, then run START_REAL_MODEL_TEST.cmd.
  popd
  goto partial
)

echo.
echo FIRST_RUN_SETUP=PASS
echo You can now run START_REAL_MODEL_TEST.cmd.
echo CALIBRATE_REAL_GAME.cmd is only needed if the canonical game/profile compatibility check fails.
popd
if /I not "%STAIRKID_NO_PAUSE%"=="1" pause
exit /b 0

:install_failed
popd
echo ERROR: Dependency/setup command failed. Review the message above.
:failed
if /I not "%STAIRKID_NO_PAUSE%"=="1" pause
exit /b 2

:partial
if /I not "%STAIRKID_NO_PAUSE%"=="1" pause
exit /b 4
