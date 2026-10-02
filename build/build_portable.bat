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
pyinstaller --clean --workpath build/temp_build build/windows.spec 2>nul || pyinstaller --clean --workpath build/temp_build build_windows.spec

if errorlevel 1 (
    echo [ERROR] Compilation failed.
    pause
    exit /b 1
)

echo.
echo [*] Structuring Portable Bundle...
if not exist "dist\Musicat" mkdir "dist\Musicat"
copy /y "dist\Musicat.exe" "dist\Musicat\Musicat.exe"
if exist "README.md" copy /y "README.md" "dist\Musicat\README.md"
if exist "README_EN.md" copy /y "README_EN.md" "dist\Musicat\README_EN.md"
if exist "LICENSE" copy /y "LICENSE" "dist\Musicat\LICENSE"
if exist "locales" xcopy /e /i /y "locales" "dist\Musicat\locales"
echo portable > "dist\Musicat\portable.lock"

echo.
echo [*] Creating Portable ZIP archive...
powershell -NoProfile -Command "Compress-Archive -Path dist\Musicat\* -DestinationPath dist\Musicat-Windows-Portable.zip -Force"

echo.
echo =====================================================================
echo [SUCCESS] Musicat Portable compiled successfully!
echo Executable: dist\Musicat.exe
echo Portable folder: dist\Musicat\
echo Portable ZIP: dist\Musicat-Windows-Portable.zip
echo =====================================================================
echo.
pause
