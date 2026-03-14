@echo off
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
echo Starting GIGATT Geomapper...

netstat -ano | findstr "127.0.0.1:8080" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo.
  echo Port 8080 is already in use. Close all GIGATT server windows first.
  echo To stop existing server processes, run in Command Prompt:
  echo   for /f "tokens=5" %a in ('netstat -ano ^| findstr "127.0.0.1:8080" ^| findstr "LISTENING"') do taskkill /F /PID %a
  echo.
  echo Then run this batch again.
  pause
  exit /b 1
)

if exist "%ROOT%\python\python.exe" (
  set "PYTHON=%ROOT%\python\python.exe"
  echo Using portable Python: %PYTHON%
) else (
  set "PYTHON=python"
  echo Using system Python.
)

"%PYTHON%" -c "import sys; sys.exit(0)" 2>nul
if errorlevel 1 (
  echo Python not found. Opening instructions...
  if exist "%ROOT%\web\install_python.html" (
    start "" "%ROOT%\web\install_python.html"
  ) else (
    echo Please install Python from https://www.python.org/downloads/
    echo Or extract a portable Python into the "python" folder in this directory.
  )
  pause
  exit /b 1
)

set "WORKDIR=%CD%"
powershell -NoProfile -Command "Start-Process -FilePath \"%PYTHON%\" -ArgumentList 'poller.py' -WorkingDirectory \"%WORKDIR%\" -WindowStyle Hidden"
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "Start-Process -FilePath \"%PYTHON%\" -ArgumentList 'server.py' -WorkingDirectory \"%WORKDIR%\" -WindowStyle Minimized"
timeout /t 4 /nobreak >nul
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
  start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" http://127.0.0.1:8080
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
  start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" http://127.0.0.1:8080
) else (
  start http://127.0.0.1:8080
)
echo Poller and server running. Server window minimized; browser opened. Close the server window to stop the app.
