@echo off
rem ====================================================================
rem  Install dsh-prompt-history 1.6.7
rem  Prompt history: Up/Down to browse, Ctrl+R to search
rem  REQUIREMENT: DSH must be fully closed first.
rem ====================================================================
setlocal
title Install dsh-prompt-history
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"

if not defined PY (
  echo   [X] Python not found.
  pause
  exit /b 1
)

if not exist "install-prompt-history.py" (
  echo   [X] install-prompt-history.py not found.
  pause
  exit /b 1
)

echo.
echo ======================================================================
echo   Install: dsh-prompt-history 1.6.7
echo   Prompt history in the composer (Up/Down + Ctrl+R search)
echo.
echo   If DSH is still running, this will refuse and change nothing.
echo ======================================================================
echo.

"%PY%" "install-prompt-history.py"

set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
  echo   Done - reopen DSH to use it.
) else (
  echo   Exit code %RC% - see above.
)
echo.
pause
exit /b %RC%
