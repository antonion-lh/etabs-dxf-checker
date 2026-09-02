@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   ETABS ↔ DXF Automated Structural Validator
echo ============================================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run 'setup_windows.bat' first to install dependencies.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

:: Check if a file was passed as argument (e.g. dragged onto the .bat file)
set "DXF_FILE=%~1"

if "%DXF_FILE%"=="" (
    echo Drag and drop your .dxf drawing file here and press Enter:
    set /p "DXF_FILE=DXF file path: "
)

:: Strip surrounding quotes if any
set "DXF_FILE=%DXF_FILE:"=%"

if not exist "!DXF_FILE!" (
    echo.
    echo [ERROR] File not found: "!DXF_FILE!"
    echo Please check the path and try again.
    echo.
    pause
    exit /b 1
)

echo.
echo ------------------------------------------------------------
echo Processing: "!DXF_FILE!"
echo ------------------------------------------------------------
echo.

python main.py --dxf "!DXF_FILE!"

if errorlevel 1 (
    echo.
    echo [ERROR] Validation encountered an issue. Check the logs above.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS! Report generated.
echo ============================================================
echo.
if exist "validation_report.pdf" (
    echo Opening validation_report.pdf...
    start "" "validation_report.pdf"
) else if exist "validation_report.html" (
    echo Opening validation_report.html...
    start "" "validation_report.html"
)

pause
