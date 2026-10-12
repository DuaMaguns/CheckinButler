@echo off
setlocal EnableExtensions
REM ============================================================
REM  wb_login.bat - add / refresh a WorkBuddy account credential
REM  Run this once per WorkBuddy account:
REM    1. A login URL will be printed - open it in browser
REM    2. Log in with the target WorkBuddy account
REM       (use an incognito window if the browser already has
REM        another WorkBuddy session, otherwise you will authorize
REM        the WRONG account)
REM    3. The page redirecting to 127.0.0.1 with an error is NORMAL
REM    4. Script saves auths\workbuddy-<uid>.json automatically
REM  Repeat for each additional account (multi-account ready).
REM ============================================================

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"
set "WB_DIR=%TOOL_DIR%\scripts\workbuddy-checkin"

set "PYEXE="
for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE for /f "usebackq delims=" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE set "PYEXE=C:\Users\at177\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PYEXE%" (
    echo [ERROR] Python not found. Edit this .bat and set PYEXE to your python.exe full path.
    exit /b 1
)

"%PYEXE%" "%WB_DIR%\login_quick.py"

echo.
echo Verify all accounts:  "%PYEXE%" "%WB_DIR%\workbuddy_checkin.py" credit
pause
