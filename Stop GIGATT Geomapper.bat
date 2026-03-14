@echo off
echo Stopping any GIGATT Geomapper server on port 8080...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8080" ^| findstr "LISTENING" 2^>nul') do (
  echo Killing PID %%a
  taskkill /F /PID %%a 2>nul
)
echo Done. You can start the app again with "Start GIGATT Geomapper.bat".
pause
