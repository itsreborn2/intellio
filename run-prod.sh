#!/bin/bash

echo "Starting production environment..."
docker compose -f docker-compose.base.yml -f docker-compose.prod.yml up -d

echo "Production environment started successfully!" 