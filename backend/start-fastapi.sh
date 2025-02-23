#!/bin/bash

# Wait for database to be ready (optional but recommended)
echo "Waiting for database to be ready..."
sleep 5

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# 환경 변수 설정
export PYTHONPATH=/backend

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir /backend \
    --log-level debug \
    --reload-include "*.py" \
    --reload-include "*.json" \
    --reload-include "*.yaml" \
    --reload-include "*.env" \
    --workers 1