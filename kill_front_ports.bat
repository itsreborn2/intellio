@echo off
chcp 949
setlocal enabledelayedexpansion

echo 포트 3000, 3010, 3020을 검사하고 있습니다....

:: 검사할 포트 목록
set "ports=3000 3010 3020"

:: 각 포트에 대해 프로세스 검사 및 종료
for %%p in (%ports%) do (
    echo.
    echo === 포트 %%p 검사중 ===
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p ^| findstr LISTENING') do (
        set pid=%%a
        
        if not "!pid!"=="" (
            echo 포트 %%p를 사용하는 프로세스 PID: !pid!
            taskkill /F /PID !pid!
            if !errorlevel! equ 0 (
                echo 프로세스가 성공적으로 종료되었습니다.
            ) else (
                echo 프로세스 종료 실패. 관리자 권한이 필요할 수 있습니다.
            )
        ) else (
            echo 포트 %%p를 사용하는 프로세스를 찾을 수 없습니다.
        )
    )
)

pause
endlocal