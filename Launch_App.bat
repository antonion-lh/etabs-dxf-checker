@echo off
setlocal enabledelayedexpansion

:: 1. Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:: 2. Auto-run setup if .venv does not exist yet
if not exist ".venv\Scripts\activate.bat" (
    echo ============================================================
    echo   First-Time Setup: Installing required packages...
    echo   (This only happens once and takes ~1 minute)
    echo ============================================================
    echo.
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt comtypes
    if errorlevel 1 (
        echo [ERROR] Setup encountered an issue.
        pause
        exit /b 1
    )
    echo [OK] Setup complete! Starting application...
    echo.
) else (
    call .venv\Scripts\activate.bat
)

:: 3. Launch Graphical User Interface (GUI)
start "" pythonw gui_app.py
if errorlevel 1 (
    python gui_app.py
)
