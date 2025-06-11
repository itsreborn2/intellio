#!/bin/bash

# 로그 디렉토리가 없으면 생성
LOG_DIR="/home/intellio_korea/fastapi_restart_logs"
mkdir -p $LOG_DIR

# 현재 날짜와 시간을 로그 파일명에 포함
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/restart_fastapi_$TIMESTAMP.log"

# 현재 디렉토리를 프로젝트 디렉토리로 변경
cd /home/intellio_korea/intellio_prod

# 로그 메시지 시작
echo "===== FastAPI 서비스 재시작 시작: $(date) =====" >> $LOG_FILE

# fastapi 서비스 중지
echo "fastapi 서비스를 중지합니다..." >> $LOG_FILE
docker compose down fastapi >> $LOG_FILE 2>&1

# 잠시 대기
sleep 5

# fastapi 서비스 시작
echo "fastapi 서비스를 시작합니다..." >> $LOG_FILE
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d fastapi >> $LOG_FILE 2>&1

# 상태 확인
echo "서비스 상태 확인:" >> $LOG_FILE
docker ps | grep fastapi >> $LOG_FILE 2>&1

echo "===== FastAPI 서비스 재시작 완료: $(date) =====" >> $LOG_FILE 
