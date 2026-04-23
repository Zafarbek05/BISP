@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "VENV313_PY=%ROOT%.venv313\Scripts\python.exe"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"

if exist "%VENV313_PY%" (
    set "PYTHON_EXE=%VENV313_PY%"
) else if exist "%VENV_PY%" (
    set "PYTHON_EXE=%VENV_PY%"
) else (
    set "PYTHON_EXE=python"
)

echo [LAUNCHER] Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" "%ROOT%app_launcher.py"

if errorlevel 1 (
    echo.
    echo The application exited with an error. Press any key to close.
    pause >nul
)

endlocal
