#!/bin/bash

# TimescaleDB 복원 스크립트
# 서버 환경에서 백업 데이터 복원용

set -e

# 매개변수 확인
if [ $# -eq 0 ]; then
    echo "사용법: $0 <백업파일경로>"
    echo "예시: $0 ./backups/timescale/timescale_backup_20250611_123456.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
# Docker Compose로 생성되는 실제 컨테이너 이름 자동 감지
CONTAINER_NAME=$(docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps -q timescaledb | head -1)
if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ TimescaleDB 컨테이너를 찾을 수 없습니다."
    exit 1
fi
DB_NAME="stockeasy_collector"
DB_USER="collector_user"

# 백업 파일 존재 확인
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ 백업 파일을 찾을 수 없습니다: $BACKUP_FILE"
    exit 1
fi

echo "=== TimescaleDB 복원 시작 ==="
echo "백업 파일: $BACKUP_FILE"
echo "대상 컨테이너: $CONTAINER_NAME"
echo "대상 데이터베이스: $DB_NAME"

# 컨테이너 실행 상태 확인
if [ -z "$CONTAINER_NAME" ] || ! docker ps --filter "id=$CONTAINER_NAME" --format "{{.ID}}" | grep -q .; then
    echo "❌ TimescaleDB 컨테이너가 실행되지 않았습니다."
    echo "다음 명령어로 서비스를 시작하세요:"
    echo "docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d timescaledb"
    exit 1
fi

# TimescaleDB 연결 대기
echo "TimescaleDB 연결 대기 중..."
for i in {1..30}; do
    if docker exec $CONTAINER_NAME pg_isready -U $DB_USER -d $DB_NAME >/dev/null 2>&1; then
        echo "✅ TimescaleDB 연결 확인"
        break
    fi
    echo "연결 시도 $i/30..."
    sleep 2
done

# 백업 파일이 압축되어 있는지 확인
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "압축된 백업 파일 복원 중..."
    zcat "$BACKUP_FILE" | docker exec -i $CONTAINER_NAME psql -U $DB_USER -d postgres
else
    echo "백업 파일 복원 중..."
    cat "$BACKUP_FILE" | docker exec -i $CONTAINER_NAME psql -U $DB_USER -d postgres
fi

echo "=== 복원 완료 ==="

# 복원 검증
echo "=== 복원 검증 ==="
echo "데이터베이스 목록:"
docker exec $CONTAINER_NAME psql -U $DB_USER -d postgres -c "\l"

echo ""
echo "TimescaleDB 확장 확인:"
docker exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"

echo ""
echo "Hypertable 목록:"
docker exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c "SELECT hypertable_name, schema_name FROM timescaledb_information.hypertables;"

echo ""
echo "✅ TimescaleDB 복원이 완료되었습니다." 