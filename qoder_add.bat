@echo off
setlocal EnableExtensions
REM ============================================================
REM  qoder_add.bat - add / refresh Qoder account credentials
REM  Requires: Qoder client installed AND logged in on this PC.
REM  1. Double-click this script
REM  2. It extracts Cosy-* device id + tokens from the client
REM     and writes scripts\Qoder-Checkin\config.json / accounts.json
REM  3. Multi-account: switch account in Qoder client, run again
REM     (accounts are merged by uid/refreshToken, never overwritten)
REM ============================================================

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"
set "QODER_DIR=%TOOL_DIR%\scripts\Qoder-Checkin"

set "PYEXE="
for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE for /f "usebackq delims=" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE set "PYEXE=C:\Users\at177\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PYEXE%" (
    echo [ERROR] Python not found. Edit this .bat and set PYEXE to your python.exe full path.
    exit /b 1
)

"%PYEXE%" "%QODER_DIR%\01_extract.py"

echo.
echo Verify:  "%PYEXE%" "%QODER_DIR%\02_checkin.py"
pause
