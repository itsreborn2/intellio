@echo off
chcp 65001 > nul
echo.
echo === 개발 환경 이미지 빌드 ===
echo.

REM BuildKit 활성화
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1

echo 베이스 이미지 빌드 중...
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml --profile build up --no-start base-image-dev

echo.
echo 서비스 이미지 빌드 중...
docker compose -f docker-compose.base.yml -f docker-compose.dev.yml build fastapi celery-doceasy celery-stockeasy
echo.
echo 개발 환경 이미지 빌드가 완료되었습니다. 