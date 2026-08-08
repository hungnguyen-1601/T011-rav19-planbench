@echo off
REM ===================================================================
REM  PlanBench - start the whole stack from Windows with one command.
REM
REM    start.bat            start the API and the web UI, open a browser
REM    start.bat stop       stop both
REM    start.bat status     is anything running?
REM    start.bat logs       follow the logs (Ctrl+C to leave)
REM
REM  The project lives inside WSL, so this file only forwards to
REM  scripts/dev_stack.sh, which does the real work. Editing that script
REM  changes the behaviour for Windows and Linux alike.
REM ===================================================================

setlocal

REM WSL path to the project. Change this if you move the repository.
REM It is a Linux path (/home/...), not a Windows one (C:\...), because
REM the command below runs inside WSL.
set PROJECT_DIR=/home/acer/T011-rav19-planbench

set "WEB_URL=http://localhost:3000"
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=start"

REM cmd.exe cannot use a UNC path (\\wsl.localhost\...) as a working
REM directory. Every path below is absolute inside WSL, so it does not
REM matter where this file was launched from.

where wsl >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: the 'wsl' command was not found.
    echo        This script starts a project that lives inside WSL.
    echo        Open a WSL terminal and run scripts/dev_stack.sh instead.
    echo.
    pause
    exit /b 1
)

wsl -e test -f "%PROJECT_DIR%/scripts/dev_stack.sh"
if errorlevel 1 (
    echo.
    echo ERROR: could not find the project at:
    echo          %PROJECT_DIR%
    echo        Edit PROJECT_DIR at the top of this file so it points at
    echo        your checkout ^(a WSL path, e.g. /home/you/PlanBench^).
    echo.
    pause
    exit /b 1
)

REM -lc so the login shell is set up the way it normally is; the script
REM overwrites PYTHONPATH itself, so a sourced ROS 2 environment does
REM not shadow the virtualenv.
wsl -e bash -lc "cd '%PROJECT_DIR%' && bash scripts/dev_stack.sh %COMMAND%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Something went wrong ^(exit code %EXIT_CODE%^). The message above
    echo says what to fix. To read further:
    echo     start.bat logs
    echo.
    pause
    exit /b %EXIT_CODE%
)

if /I "%COMMAND%"=="start" (
    echo   Opening %WEB_URL%
    start "" "%WEB_URL%"
    echo.
    echo   The servers keep running after this window closes.
    echo   Stop them with:  start.bat stop
    echo.
    pause
)

endlocal
exit /b 0
