@echo off
chcp 65001 > nul
echo.
echo === Docker 도움말 ===
echo.
echo 1. 개발 환경 이미지 빌드: build-dev.cmd
echo 2. 개발 환경 실행: run-dev.cmd
echo 3. 개발 환경 중지: docker-compose -f docker-compose.base.yml -f docker-compose.dev.yml down
echo 4. 개발 환경 로그 확인: docker-compose -f docker-compose.base.yml -f docker-compose.dev.yml logs -f
echo 5. 특정 서비스 로그 확인: docker-compose -f docker-compose.base.yml -f docker-compose.dev.yml logs -f [서비스명]
echo 6. 컨테이너 상태 확인: docker ps
echo 7. 이미지 목록 확인: docker images
echo 8. 볼륨 목록 확인: docker volume ls
echo 9. 모든 컨테이너 중지: for /f "tokens=*" %%i in ('docker ps -q') do docker stop %%i
echo 10. 사용하지 않는 리소스 정리: docker system prune -a
echo.
echo === Windows 환경에서 Docker 사용 시 주의사항 ===
echo - 볼륨 마운트 경로는 자동으로 변환되지만, 경로에 공백이 있으면 문제가 발생할 수 있습니다.
echo - WSL2 백엔드를 사용하는 것이 권장됩니다.
echo - 볼륨 마운트 문제가 발생하면 Docker Desktop 설정에서 'Shared Drives' 또는 'Resources ^> File Sharing'을 확인하세요.
echo. 