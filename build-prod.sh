#!/bin/bash

echo "Building production images..."

# 베이스 이미지 빌드
echo "Building base production image..."
docker-compose -f docker-compose.base.yml -f docker-compose.prod.yml --profile build up --no-start base-image-prod

# 서비스 이미지 빌드
echo "Building service production images..."
docker-compose -f docker-compose.base.yml -f docker-compose.prod.yml build fastapi celery-doceasy celery-stockeasy

echo "Production images built successfully!" 