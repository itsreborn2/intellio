@echo off
rem intellio-base-dev 컨테이너 중지 및 삭제
rem docker stop $(docker ps -a -f name=intellio-base-dev -q)
rem docker rm $(docker ps -a -f name=intellio-base-dev -q)

rem 모든 이미지 삭제
docker rmi intellio-base-dev intellio-celery-doceasy intellio-celery-stockeasy intellio-fastapi