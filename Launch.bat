@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%ROOT%app_launcher.py"
) else (
    python "%ROOT%app_launcher.py"
)

if errorlevel 1 (
    echo.
    echo The application exited with an error. Press any key to close.
    pause >nul
)

endlocal
