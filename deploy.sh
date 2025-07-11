#!/bin/bash
set -e

echo "🚀 배포를 시작합니다..."

# 1. 프로젝트 빌드
echo "📦 프로젝트를 빌드합니다..."
npm run build

# 2. PM2로 애플리케이션 리로드 (무중단)
echo "🔄 PM2로 애플리케이션을 리로드합니다..."
pm2 reload ecosystem.config.js

echo "✅ 배포가 성공적으로 완료되었습니다!"
pm2 list 