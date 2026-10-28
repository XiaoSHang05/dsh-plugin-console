@echo off
rem ====================================================================
rem  Plugin Console - launcher (PURE ASCII on purpose)
rem  Uses pythonw.exe so no console window flashes.
rem ====================================================================
setlocal
cd /d "%~dp0"

rem --- prefer pythonw.exe (no console window) ---
set "PYW="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not defined PYW if exist "C:\Python312\pythonw.exe" set "PYW=C:\Python312\pythonw.exe"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"

rem --- fallback: plain python (will show a console) ---
if not defined PYW (
  where python >nul 2>nul && set "PYW=python"
)

if not defined PYW (
  echo.
  echo   [X] Python not found.
  echo       Install Python 3.10+ and try again.
  echo.
  pause
  exit /b 1
)

if not exist "app.py" (
  echo.
  echo   [X] app.py not found next to this launcher.
  echo.
  pause
  exit /b 1
)

start "" "%PYW%" "%~dp0app.py"
exit /b 0
