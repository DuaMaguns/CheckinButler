@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
REM ============================================================
REM  setup.bat - one-time initialization
REM    1. locate a usable Python
REM    2. create config\checkin_env.bat from the example template
REM    3. create directory skeleton
REM    4. run doctor.py self-check
REM  NOTE: keep this file ASCII-only (see cli.bat comment).
REM ============================================================

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"

echo ============================================================
echo   Checkin Tool - Setup
echo   Root: %TOOL_DIR%
echo ============================================================
echo.

REM --- 1) locate Python ---
set "PY="
where py >nul 2>nul && (
    py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
)
if not defined PY (
    echo [FAIL] Python not found. Install Python 3.8+ and check "Add to PATH".
    echo        Download: https://www.python.org/downloads/
    goto :fail
)

echo [1/4] Python: %PY%
%PY% -c "import sys; print('       version:', sys.version.split()[0])"
echo.

REM --- 2) create config ---
echo [2/4] Checking config file...
if exist "%TOOL_DIR%\config\checkin_env.bat" (
    echo       config\checkin_env.bat already exists, skipped (your keys are safe)
) else (
    copy /Y "%TOOL_DIR%\config\checkin_env.example.bat" "%TOOL_DIR%\config\checkin_env.bat" >nul
    echo       Created config\checkin_env.bat from template
)
echo.

REM --- 3) directory skeleton ---
echo [3/4] Checking directories...
if not exist "%TOOL_DIR%\logs" mkdir "%TOOL_DIR%\logs"
if not exist "%TOOL_DIR%\scripts\workbuddy-checkin\auths" mkdir "%TOOL_DIR%\scripts\workbuddy-checkin\auths"
if not exist "%TOOL_DIR%\config\trae-accounts" mkdir "%TOOL_DIR%\config\trae-accounts"
echo       OK
echo.

REM --- 4) self-check ---
echo [4/4] Doctor self-check
echo ------------------------------------------------------------
%PY% "%TOOL_DIR%\scripts\doctor.py"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   Setup finished. Next steps:
echo     1) Edit config\checkin_env.bat  (fill your push key)
echo     2) Double-click wb_login.bat    (add WorkBuddy account)
echo     3) Double-click trae_add.bat    (add Trae account)
echo     4) Double-click run_checkin.bat (first real run)
REM  TIP: or just double-click cli.bat and follow the wizard.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo Setup failed. Fix the issues above, then run setup.bat again.
pause
exit /b 1
