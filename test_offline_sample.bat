@echo off
setlocal

echo ============================================================
echo   Running Instant Offline Trial (No ETABS Required)
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

echo Testing sample_building.dxf against pre-exported ETABS model data...
echo.

python main.py --dxf sample_building.dxf --etabs-csv-prefix etabs_sample --output sample_trial_report

if errorlevel 1 (
    echo.
    echo [ERROR] Trial run encountered an issue.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TRIAL RUN COMPLETE! Opening PDF Report...
echo ============================================================
echo.

if exist "sample_trial_report.pdf" (
    start "" "sample_trial_report.pdf"
) else if exist "sample_trial_report.html" (
    start "" "sample_trial_report.html"
)

pause
