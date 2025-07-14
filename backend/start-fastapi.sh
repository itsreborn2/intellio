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
BACKLOG=${BACKLOG:-2048} # Uvicorn 연결 대기열(backlog) 크기. 동시 접속자가 많을 때 이 값을 조정하여 더 많은 연결을 대기시킬 수 있습니다.

# 환경에 따라 RELOAD 기본값 설정
if [ "$CURRENT_ENV" = "production" ]; then
    # 프로덕션 환경에서는 RELOAD 기본값을 false로 설정
    RELOAD=${RELOAD:-"false"}
else
    # 개발 환경에서는 RELOAD 기본값을 true로 설정
    RELOAD=${RELOAD:-"false"}
fi

echo "RELOAD 설정값: $RELOAD"
LOG_LEVEL=${LOG_LEVEL:-"debug"}

# Celery 워커 동시성 설정 확인
CELERY_DOCEASY_CONCURRENCY=${CELERY_CONCURRENCY_DOCEASY:-1}
CELERY_STOCKEASY_CONCURRENCY=${CELERY_CONCURRENCY_STOCKEASY:-1}
TOTAL_CELERY_WORKERS=$((CELERY_DOCEASY_CONCURRENCY + CELERY_STOCKEASY_CONCURRENCY))
echo "Celery 워커 총 수: $TOTAL_CELERY_WORKERS (DocEasy: $CELERY_DOCEASY_CONCURRENCY, StockEasy: $CELERY_STOCKEASY_CONCURRENCY)"

# CPU 워커 수 설정 - 기본값은 시스템 CPU 수 또는 개발환경에서는 1
if [ "$RELOAD" = "true" ] || [ "$CURRENT_ENV" != "production" ]; then
    # 개발 환경에서는 워커 수를 1로 설정 (reload 모드와 여러 워커는 호환되지 않음)
    WORKERS=${WORKERS:-"3"}
    echo "개발 환경(reload=true 또는 개발환경)에서 실행 중: 워커 수 = $WORKERS"
else
    # 프로덕션 환경에서는 CPU 코어 수와 Celery 워커 수를 고려하여 설정
    # FastAPI에 먼저 필요한 코어 할당
    FASTAPI_CORES=${FASTAPI_MIN_CORES:-2}
    AVAILABLE_CORES=$((CPU_COUNT - FASTAPI_CORES))
    
    # 최소 1개 이상의 코어 사용 보장
    if [ $AVAILABLE_CORES -lt 1 ]; then
        AVAILABLE_CORES=1
        echo "경고: 시스템 리소스가 제한적입니다..."
    fi
    
    # I/O 바운드 워크로드 (벡터DB 검색, LLM 호출) 최적화 설정
    # 기본 승수 값 (환경 변수로 설정 가능)
    WORKER_MULTIPLIER=${WORKER_MULTIPLIER:-3}
    
    # 가용 코어에 multiplier 적용 (I/O 대기 시간이 긴 작업에 최적화)
    RECOMMENDED_WORKERS=$((AVAILABLE_CORES * WORKER_MULTIPLIER))
    
    # 시스템 안정성을 위한 상한선 설정
    MAX_WORKERS=${MAX_WORKERS:-32}
    if [ $RECOMMENDED_WORKERS -gt $MAX_WORKERS ]; then
        RECOMMENDED_WORKERS=$MAX_WORKERS
        echo "워커 수가 최대 한도($MAX_WORKERS)로 제한됩니다."
    fi
    
    WORKERS=${WORKERS:-$RECOMMENDED_WORKERS}
    echo "프로덕션 환경(reload=false)에서 실행 중: 워커 수 = $WORKERS (가용 코어 수: $AVAILABLE_CORES, 승수: $WORKER_MULTIPLIER)"
    echo "워크로드 유형: I/O 바운드 (벡터DB 검색, LLM 호출 대기 시간이 긴 작업)"
fi

# 환경 변수에 따른 실행 옵션 설정
UVICORN_OPTS="--host $HOST --port $PORT --backlog $BACKLOG"

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