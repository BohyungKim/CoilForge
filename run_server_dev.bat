@echo off
setlocal enabledelayedexpansion
REM CoilForge Phase 2A local server launcher -- DEV (auto-reload).
REM Development-only: auto-reloads on src edits. pdfCoilPages is a client-side cache,
REM   so re-analyze the PDF in the browser after an edit or your change won't show.
REM Double-click this file, then open the URL printed below in your browser.
REM
REM Optional port argument, so several projects can run side by side:
REM     run_server_dev.bat        -> 8011 (default)
REM     run_server_dev.bat 8012   -> 8012
REM A busy port is auto-avoided by scanning upward; the port actually used is printed below.

REM Always run from this script's own folder (the project root).
cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8011"

REM Auto-avoid a port another session already holds (scan PORT .. PORT+9).
set /a TRY=0
:findport
netstat -ano -p TCP | findstr /R /C:":!PORT! " | findstr /C:"LISTENING" >nul 2>&1
if errorlevel 1 goto gotport
echo [port !PORT! is already in use - trying !PORT!+1 ...]
set /a PORT=!PORT!+1
set /a TRY=!TRY!+1
if !TRY! LSS 10 goto findport
echo.
echo [ERROR] No free port found in the scanned range.
echo         Close one of the running servers, or pass a port explicitly:
echo             run_server_dev.bat 8025
echo.
pause >nul
exit /b 1
:gotport

echo ================================================================
echo  CoilForge Phase 2A  -  starting local server (DEV / auto-reload)
echo  Project: %CD%
echo.
echo  When you see "Application startup complete", open:
echo.
echo      http://127.0.0.1:!PORT!/
echo.
echo  Press CTRL+C in this window to stop the server.
echo ================================================================
echo.

REM Try the standard launcher first, fall back to "py" if needed.
python -m uvicorn coilforge.web_app:app --app-dir src --host 127.0.0.1 --port !PORT! --reload
if errorlevel 1 (
  echo.
  echo [python failed - trying the Windows "py" launcher...]
  py -m uvicorn coilforge.web_app:app --app-dir src --host 127.0.0.1 --port !PORT! --reload
)

echo.
echo Server stopped. Press any key to close this window.
pause >nul
