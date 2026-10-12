@echo off
setlocal EnableExtensions
REM ============================================================
REM  trae_add.bat - add / refresh a Trae account
REM  1. Log in with the account inside the Trae client
REM  2. Double-click this script
REM  It archives the login into config\trae-accounts\ and updates
REM  TRAE_ACCOUNTS in config\checkin_env.bat automatically.
REM  Repeat for each additional account (multi-account ready).
REM ============================================================

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"

set "PYEXE="
for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE for /f "usebackq delims=" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE set "PYEXE=C:\Users\at177\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PYEXE%" (
    echo [ERROR] Python not found. Edit this .bat and set PYEXE to your python.exe full path.
    exit /b 1
)

"%PYEXE%" "%TOOL_DIR%\scripts\trae_accounts_update.py"
echo.
pause
