@echo off
cd /d "%~dp0"

REM Find git.exe: use PATH first, then common install locations
set "GIT_CMD="
where git >nul 2>&1 && set "GIT_CMD=git"
if not defined GIT_CMD if exist "C:\Program Files\Git\cmd\git.exe" set "GIT_CMD=C:\Program Files\Git\cmd\git.exe"
if not defined GIT_CMD if exist "C:\Program Files\Git\bin\git.exe" set "GIT_CMD=C:\Program Files\Git\bin\git.exe"
if not defined GIT_CMD if exist "C:\Program Files (x86)\Git\cmd\git.exe" set "GIT_CMD=C:\Program Files (x86)\Git\cmd\git.exe"
if not defined GIT_CMD if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT_CMD=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"

if not defined GIT_CMD (
    echo.
    echo   Git was not found. Please install Git for Windows:
    echo.
    echo   1. Open: https://git-scm.com/download/win
    echo   2. Run the installer (use default options).
    echo   3. IMPORTANT: Close this window and open a NEW Command Prompt,
    echo      then run this batch file again from the project folder.
    echo.
    pause
    exit /b 1
)

echo Using: %GIT_CMD%
echo.

if not exist .git (
    echo Initializing git repository...
    "%GIT_CMD%" init
)

echo Adding files...
"%GIT_CMD%" add .cursor
"%GIT_CMD%" add data
"%GIT_CMD%" add python
"%GIT_CMD%" add web
"%GIT_CMD%" add .gitignore
"%GIT_CMD%" add config.json.example
"%GIT_CMD%" add poller.py
"%GIT_CMD%" add README.txt
"%GIT_CMD%" add server.py
"%GIT_CMD%" add "Start GIGATT Geomapper.bat"
"%GIT_CMD%" add start.bat
"%GIT_CMD%" add "Stop GIGATT Geomapper.bat"

echo.
"%GIT_CMD%" status
echo.
set "MSG=Initial commit: GIGATT Geomapper"
set /p MSG="Commit message (or Enter for default): "
if "%MSG%"=="" set "MSG=Initial commit: GIGATT Geomapper"
"%GIT_CMD%" commit -m "%MSG%"

echo.
echo Adding remote and pushing to GitHub...
"%GIT_CMD%" remote remove origin 2>nul
"%GIT_CMD%" remote add origin https://github.com/AlexGuruz/Geomapping-APP.git
"%GIT_CMD%" branch -M main
"%GIT_CMD%" push -u origin main

echo.
echo Done.
pause
