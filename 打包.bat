@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
REM ============================================================
REM  make_package.bat - build a shareable zip via make_package.py
REM  Auto-excludes: credentials / push keys / logs / state files.
REM  NOTE: keep this file ASCII-only (see cli.bat comment).
REM ============================================================

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"

set "PYEXE="
for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE for /f "usebackq delims=" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
if not defined PYEXE set "PYEXE=C:\Users\at177\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PYEXE%" (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

"%PYEXE%" "%TOOL_DIR%\scripts\make_package.py"
pause
