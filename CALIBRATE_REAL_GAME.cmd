@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo ERROR: Run FIRST_RUN_SETUP.cmd first.
  if /I not "%STAIRKID_NO_PAUSE%"=="1" pause
  exit /b 2
)

:menu
cls
echo ================================================================
echo StairKid RL - Passive Real Detector Calibration
echo No keyboard/game action is sent. Keep NS-SHAFT open and visible.
echo Before choosing an item, display that object clearly in the game.
echo ================================================================
echo 1 = central dialog/menu
echo 2 = normal platform + playfield
echo 3 = spikes platform
echo 4 = spring platform
echo 5 = conveyor animation frame 1
echo 6 = conveyor animation frame 2
echo 7 = flipping animation frame 1
echo 8 = flipping animation frame 2
echo 9 = check calibration completeness
echo 0 = exit
set "CHOICE="
set /p "CHOICE=SELECTION [0-9]: "
if "%CHOICE%"=="0" goto done
if "%CHOICE%"=="1" set "KIND=dialog"
if "%CHOICE%"=="2" set "KIND=normal"
if "%CHOICE%"=="3" set "KIND=spikes"
if "%CHOICE%"=="4" set "KIND=spring"
if "%CHOICE%"=="5" set "KIND=conveyor-1"
if "%CHOICE%"=="6" set "KIND=conveyor-2"
if "%CHOICE%"=="7" set "KIND=flipping-1"
if "%CHOICE%"=="8" set "KIND=flipping-2"
if "%CHOICE%"=="9" goto check
if not defined KIND goto invalid

pushd "%PROJECT_ROOT%" || exit /b 3
"%PYTHON_EXE%" -m stair_agent.real.calibration --project-root . --kind "%KIND%"
set "RESULT=%ERRORLEVEL%"
popd
set "KIND="
if not "%RESULT%"=="0" echo Calibration item failed; review the message above.
pause
goto menu

:check
pushd "%PROJECT_ROOT%" || exit /b 3
"%PYTHON_EXE%" -m stair_agent.real.setup --project-root . --check
set "RESULT=%ERRORLEVEL%"
popd
if "%RESULT%"=="0" echo REAL_CALIBRATION=PASS
pause
goto menu

:invalid
echo INVALID_SELECTION
pause
goto menu

:done
exit /b 0
