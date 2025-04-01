#!/bin/bash

# Wait for database to be ready (optional but recommended)
echo "Waiting for database to be ready..."
sleep 5

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# 환경 변수 설정
export PYTHONPATH=/backend

# 기본 설정값 정의
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8000"}
RELOAD=${RELOAD:-"true"}
LOG_LEVEL=${LOG_LEVEL:-"debug"}

# 환경 변수에 따른 실행 옵션 설정
UVICORN_OPTS="--host $HOST --port $PORT"

# RELOAD 옵션 설정
if [ "$RELOAD" = "true" ]; then
    UVICORN_OPTS="$UVICORN_OPTS --reload \
    --reload-dir /backend/main.py \
    --reload-dir /backend/common \
    --reload-dir /backend/doceasy \
    --reload-dir /backend/stockeasy"
fi

# LOG_LEVEL 설정
UVICORN_OPTS="$UVICORN_OPTS --log-level $LOG_LEVEL"

# Start the FastAPI application
echo "Starting FastAPI application with options: $UVICORN_OPTS"
uvicorn main:app $UVICORN_OPTS 