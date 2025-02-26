@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
echo Killing frontend processes on ports 3000, 3010, 3020...

REM Kill processes on port 3000
echo Checking for processes on port 3000...
FOR /F "tokens=5" %%P IN ('netstat -ano ^| find ":3000" ^| find "LISTENING"') DO (
    echo Killing process with PID: %%P on port 3000...
    taskkill /F /PID %%P >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo Successfully terminated process on port 3000
    ) else (
        echo No process found on port 3000 or failed to terminate
    )
)

REM Kill processes on port 3010
echo Checking for processes on port 3010...
FOR /F "tokens=5" %%P IN ('netstat -ano ^| find ":3010" ^| find "LISTENING"') DO (
    echo Killing process with PID: %%P on port 3010...
    taskkill /F /PID %%P >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo Successfully terminated process on port 3010
    ) else (
        echo No process found on port 3010 or failed to terminate
    )
)

REM Kill processes on port 3020
echo Checking for processes on port 3020...
FOR /F "tokens=5" %%P IN ('netstat -ano ^| find ":3020" ^| find "LISTENING"') DO (
    echo Killing process with PID: %%P on port 3020...
    taskkill /F /PID %%P >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo Successfully terminated process on port 3020
    ) else (
        echo No process found on port 3020 or failed to terminate
    )
)

echo All tasks completed.
endlocal
pause 