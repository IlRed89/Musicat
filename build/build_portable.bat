@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo                MUSICAT - STANDALONE PORTABLE BUILDER
echo =====================================================================
echo.

:: Move to project root
cd /d "%~dp0\.."

echo [*] Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found on PATH. Please install Python 3.11+.
    pause
    exit /b 1
)

echo [*] Installing / Verifying requirements...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Some requirements failed to install. Continuing...
)

echo.
echo [*] Cleaning previous build artifacts...
if exist "dist\Musicat" rmdir /s /q "dist\Musicat"
if exist "dist\Musicat.exe" del /f /q "dist\Musicat.exe"
if exist "build\temp_build" rmdir /s /q "build\temp_build"

echo.
echo [*] Compiling Musicat Portable with PyInstaller...
pyinstaller --clean --workpath build/temp_build build/musicat.spec

if errorlevel 1 (
    echo [ERROR] Compilation failed.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo [SUCCESS] Musicat Portable compiled successfully!
echo Executable located in: dist\Musicat.exe
echo =====================================================================
echo.
pause
