@echo off
setlocal EnableExtensions
REM ============================================================
REM  get_tokens.bat - helper: extract Trae credentials from the
REM  logged-in Trae client. Run this ONCE per account change:
REM    1. Open Trae client and log in with account #1
REM    2. Run this script, copy printed JSON into config\checkin_env.bat
REM  It prints TRAE_ACCOUNTS (one-line JSON) and device keys.
REM  Alternative: trae_add.bat archives automatically.
REM ============================================================

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"
set "SCRIPT_DIR=%TOOL_DIR%\scripts\Trae-AutoCheckin"

set "PYEXE="
for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE for /f "usebackq delims=" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE set "PYEXE=C:\Users\at177\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PYEXE%" (
    echo [ERROR] Python not found. Edit this .bat and set PYEXE to your python.exe full path.
    exit /b 1
)

echo === [1/2] Extracting TRAE_ACCOUNTS (multi-account JSON) ===
"%PYEXE%" "%SCRIPT_DIR%\trae_get_token.py" --accounts

echo.
echo === [2/2] Exporting device keys (required for renewal) ===
"%PYEXE%" "%SCRIPT_DIR%\trae_get_token.py" --export-keys

echo.
echo Done. Copy the printed values into config\checkin_env.bat
pause
