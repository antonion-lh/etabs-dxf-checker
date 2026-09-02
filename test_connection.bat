@echo off
setlocal

echo ============================================================
echo   Testing ETABS v23 Connection
echo ============================================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run 'setup_windows.bat' first!
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python check_connection.py

echo.
pause
