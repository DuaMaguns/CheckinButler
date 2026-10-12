@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
REM ============================================================
REM  cli.bat - Checkin Tool console entry (double-click to run)
REM  First run: guided wizard. Later: number menu.
REM  NOTE 1: keep this file ASCII-only! cmd parses bat with ANSI
REM          codepage; UTF-8 Chinese here breaks parsing (flash).
REM  NOTE 2: this tool needs Python 3.8+. If missing, open the
REM          install guide (README-FIRST.txt) + download page.
REM ============================================================

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"

set "PYEXE="
for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE for /f "usebackq delims=" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE set "PYEXE=C:\Users\at177\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if exist "%PYEXE%" goto :run

echo ============================================================
echo   [ERROR] Python not found - this tool needs Python 3.8+
echo ============================================================
echo.
echo   How to fix (5 minutes, free):
echo.
echo   1. Opening the install guide now (README-FIRST.txt) ...
echo   2. Download Python:  https://www.python.org/downloads/
echo   3. Run the installer - IMPORTANT: check the box
echo         [x] Add python.exe to PATH
echo      (without it, install is useless!)
echo   4. Double-click cli.bat again. Done.
echo.
echo ============================================================
start "" notepad "%TOOL_DIR%\README-FIRST.txt"
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:run
"%PYEXE%" "%TOOL_DIR%\cli.py"
if errorlevel 1 (
    echo.
    echo [ERROR] cli.py exited with an error. See traceback above.
)
pause
