@echo off
setlocal
title Open Input Bridge - LY-03 to Windows
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher not found. Install Python 3.10+ for Windows.
  pause
  exit /b 1
)
rem Safely replace a prior bridge from this checkout; never kill unrelated processes.
rem Forward optional flags such as --dry-run, --port, and --hotkey.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-windows.ps1" %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo [ERROR] Bridge exited with code %RESULT%.
echo.
echo Bridge stopped. Press any key to close this window.
pause >nul
exit /b %RESULT%
