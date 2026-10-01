@echo off
setlocal
cd /d "%~dp0\.."
echo ========================================================
echo    Musicat - GitHub Repo & Release Initializer
echo ========================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish_release.ps1"
echo.
pause
