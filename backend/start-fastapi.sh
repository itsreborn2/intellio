#!/bin/bash

# Wait for database to be ready (optional but recommended)
echo "Waiting for database to be ready..."
sleep 5

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# 환경 변수 설정
export PYTHONPATH=/backend

# CPU 코어 수 확인 (Linux)
CPU_COUNT=$(nproc 2>/dev/null || echo "1")
echo "시스템 CPU 코어 수: $CPU_COUNT"

# 현재 환경 확인 (ENV 또는 NODE_ENV 변수 사용)
CURRENT_ENV=${ENV:-${NODE_ENV:-"development"}}
echo "현재 환경: $CURRENT_ENV"

# 기본 설정값 정의
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8000"}

# 환경에 따라 RELOAD 기본값 설정
if [ "$CURRENT_ENV" = "production" ]; then
    # 프로덕션 환경에서는 RELOAD 기본값을 false로 설정
    RELOAD=${RELOAD:-"false"}
else
    # 개발 환경에서는 RELOAD 기본값을 true로 설정
    RELOAD=${RELOAD:-"true"}
fi

echo "RELOAD 설정값: $RELOAD"
LOG_LEVEL=${LOG_LEVEL:-"debug"}

# CPU 워커 수 설정 - 기본값은 시스템 CPU 수 또는 개발환경에서는 1
if [ "$RELOAD" = "true" ]; then
    # 개발 환경에서는 워커 수를 1로 설정 (reload 모드와 여러 워커는 호환되지 않음)
    WORKERS=${WORKERS:-"1"}
    echo "개발 환경(reload=true)에서 실행 중: 워커 수 = $WORKERS"
else
    # 프로덕션 환경에서는 CPU 코어 수에 맞게 설정
    # 권장 워커 수: CPU 코어 수 * 2 + 1 (Gunicorn 공식 권장사항)
    RECOMMENDED_WORKERS=$((CPU_COUNT * 2 + 1))
    WORKERS=${WORKERS:-$RECOMMENDED_WORKERS}
    echo "프로덕션 환경(reload=false)에서 실행 중: 워커 수 = $WORKERS (권장: $RECOMMENDED_WORKERS)"
fi

# 환경 변수에 따른 실행 옵션 설정
UVICORN_OPTS="--host $HOST --port $PORT"

# RELOAD 옵션 설정
if [ "$RELOAD" = "true" ]; then
    UVICORN_OPTS="$UVICORN_OPTS --reload \
    --reload-dir /backend/main.py \
    --reload-dir /backend/common \
    --reload-dir /backend/doceasy \
    --reload-dir /backend/stockeasy"
else
    # 프로덕션 환경에서는 워커 수 적용
    UVICORN_OPTS="$UVICORN_OPTS --workers $WORKERS"
fi

# LOG_LEVEL 설정
UVICORN_OPTS="$UVICORN_OPTS --log-level $LOG_LEVEL"

# Start the FastAPI application
echo "Starting FastAPI application with options: $UVICORN_OPTS"
uvicorn main:app $UVICORN_OPTS 