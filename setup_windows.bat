@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   ETABS-DXF Checker - Windows Automated Setup
echo ============================================================
echo.

:: 1. Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10 or 3.11 from https://www.python.org/
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [OK] Python detected:
python --version
echo.

:: 2. Create Virtual Environment
if not exist ".venv" (
    echo Creating virtual environment (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment (.venv) already exists.
)

:: 3. Activate Virtual Environment & Install Dependencies
echo.
echo Installing required packages (this may take 1-2 minutes)...
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt comtypes

if errorlevel 1 (
    echo.
    echo [ERROR] Package installation encountered an issue.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SETUP COMPLETE!
echo ============================================================
echo You can now:
echo  1. Double-click 'test_connection.bat' to test ETABS connection.
echo  2. Drag and drop your .dxf file onto 'run_validation.bat'.
echo.
pause
