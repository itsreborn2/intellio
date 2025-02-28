@echo off
chcp 65001 > nul
echo.
echo === 개발 환경 실행 ===
echo 개발 환경을 시작합니다...
echo.
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml up -d
echo 개발 환경이 성공적으로 시작되었습니다.
echo FastAPI: http://localhost:8000
echo Flower: http://localhost:5555
echo PgAdmin: http://localhost:5055
echo. 