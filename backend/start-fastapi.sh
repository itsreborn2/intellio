#!/bin/bash

# Wait for database to be ready (optional but recommended)
echo "Waiting for database to be ready..."
sleep 10

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug 