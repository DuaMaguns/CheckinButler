@echo off
setlocal EnableExtensions
REM ============================================================
REM  run_checkin.bat - main entry, called by Task Scheduler
REM  Delegates everything to scripts\run_all.py:
REM    Trae check-in + WorkBuddy API check-in + combined WeCom push
REM  Log: logs\checkin_YYYY-MM-DD.log (written by run_all.py)
REM
REM  Python lookup order: py -3 -> python -> hardcoded fallback
REM  (edit the fallback below only if auto-detection fails)
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

REM --- Load config (notification keys etc. into env) ---
call "%TOOL_DIR%\config\checkin_env.bat"

"%PYEXE%" "%TOOL_DIR%\scripts\run_all.py" %*
exit /b %errorlevel%
