@echo off
setlocal

rem Start the Flask backend from this file's directory.
cd /d "%~dp0"

set "ENV_NAME=geoenv"
set "ACTIVATE_BAT="

rem 1) If the shell is already in a conda environment, use that installation.
if defined CONDA_PREFIX (
  if exist "%CONDA_PREFIX%\Scripts\activate.bat" (
    set "ACTIVATE_BAT=%CONDA_PREFIX%\Scripts\activate.bat"
  )
)

rem 2) If conda is on PATH, derive the activation script location.
if not defined ACTIVATE_BAT (
  for /f "delims=" %%I in ('where conda 2^>nul') do (
    if not defined ACTIVATE_BAT (
      if exist "%%~dpI..\Scripts\activate.bat" set "ACTIVATE_BAT=%%~dpI..\Scripts\activate.bat"
      if exist "%%~dpI..\..\Scripts\activate.bat" set "ACTIVATE_BAT=%%~dpI..\..\Scripts\activate.bat"
    )
  )
)

rem 3) Typical per-user conda installs.
if not defined ACTIVATE_BAT if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" set "ACTIVATE_BAT=%USERPROFILE%\anaconda3\Scripts\activate.bat"
if not defined ACTIVATE_BAT if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" set "ACTIVATE_BAT=%USERPROFILE%\miniconda3\Scripts\activate.bat"

if not defined ACTIVATE_BAT (
  echo [ERROR] Could not find conda activate.bat.
  echo Tried current CONDA_PREFIX, PATH, %%USERPROFILE%%\anaconda3, and %%USERPROFILE%%\miniconda3.
  echo Please open an Anaconda Prompt or add conda to PATH, then run this file again.
  pause
  exit /b 1
)

echo [INFO] Using conda activation script:
echo        %ACTIVATE_BAT%
echo [INFO] Activating environment: %ENV_NAME%
call "%ACTIVATE_BAT%" "%ENV_NAME%"
if errorlevel 1 (
  echo [ERROR] Failed to activate conda environment "%ENV_NAME%".
  echo Check that the environment exists: conda env list
  pause
  exit /b 1
)

echo [INFO] Starting backend at http://localhost:5000
python app.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo [INFO] Backend process exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
