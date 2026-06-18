@echo off
REM CoilForge Phase 2A local server launcher.
REM Double-click this file, then open the URL printed below in your browser.

REM Always run from this script's own folder (the project root).
cd /d "%~dp0"

set PORT=8011
echo ================================================================
echo  CoilForge Phase 2A  -  starting local server
echo  Project: %CD%
echo.
echo  When you see "Application startup complete", open:
echo.
echo      http://127.0.0.1:%PORT%/
echo.
echo  Press CTRL+C in this window to stop the server.
echo ================================================================
echo.

REM Try the standard launcher first, fall back to "py" if needed.
python -m uvicorn coilforge.web_app:app --app-dir src --host 127.0.0.1 --port %PORT%
if errorlevel 1 (
  echo.
  echo [python failed - trying the Windows "py" launcher...]
  py -m uvicorn coilforge.web_app:app --app-dir src --host 127.0.0.1 --port %PORT%
)

echo.
echo Server stopped. Press any key to close this window.
pause >nul
