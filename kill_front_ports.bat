@echo off
chcp 949
setlocal enabledelayedexpansion

echo ��Ʈ 3000, 3010, 3020�� �˻��ϰ� �ֽ��ϴ�.

:: �˻��� ��Ʈ ���
set "ports=3000 3010 3020"

:: �� ��Ʈ�� ���� ���μ��� �˻� �� ����
for %%p in (%ports%) do (
    echo.
    echo === ��Ʈ %%p �˻��� ===
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p ^| findstr LISTENING') do (
        set pid=%%a
        
        if not "!pid!"=="" (
            echo ��Ʈ %%p�� ����ϴ� ���μ��� PID: !pid!
            taskkill /F /PID !pid!
            if !errorlevel! equ 0 (
                echo ���μ����� ���������� ����Ǿ����ϴ�.
            ) else (
                echo ���μ��� ���� ����. ������ ������ �ʿ��� �� �ֽ��ϴ�.
            )
        ) else (
            echo ��Ʈ %%p�� ����ϴ� ���μ����� ã�� �� �����ϴ�.
        )
    )
)

pause
endlocal