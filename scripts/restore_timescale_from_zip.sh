#!/bin/bash

# TimescaleDB 복원 스크립트 (ZIP 파일용)
# 윈도우에서 생성된 ZIP 백업 파일을 서버에서 복원

set -e

# 매개변수 확인
if [ $# -eq 0 ]; then
    echo "사용법: $0 <백업ZIP파일경로>"
    echo "예시: $0 ./backups/timescale/timescale_backup_20250611_123456.sql.zip"
    exit 1
fi

BACKUP_ZIP="$1"
# Docker Compose로 생성되는 실제 컨테이너 이름 자동 감지
CONTAINER_NAME=$(docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps -q timescaledb | head -1)
if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ TimescaleDB 컨테이너를 찾을 수 없습니다."
    exit 1
fi
DB_NAME="stockeasy_collector"
DB_USER="collector_user"

# 백업 파일 존재 확인
if [ ! -f "$BACKUP_ZIP" ]; then
    echo "❌ 백업 ZIP 파일을 찾을 수 없습니다: $BACKUP_ZIP"
    exit 1
fi

echo "=== TimescaleDB 복원 시작 (ZIP 파일) ==="
echo "백업 ZIP 파일: $BACKUP_ZIP"
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

# 임시 디렉토리 생성
TEMP_DIR="/tmp/timescale_restore_$(date +%s)"
mkdir -p $TEMP_DIR

# ZIP 파일 압축 해제
echo "ZIP 파일 압축 해제 중..."
unzip -q "$BACKUP_ZIP" -d "$TEMP_DIR"

# SQL 파일 찾기
SQL_FILE=$(find "$TEMP_DIR" -name "*.sql" -type f | head -1)
if [ -z "$SQL_FILE" ]; then
    echo "❌ ZIP 파일에서 SQL 파일을 찾을 수 없습니다."
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "SQL 파일 발견: $(basename $SQL_FILE)"

# 백업 파일 복원
echo "백업 파일 복원 중..."
cat "$SQL_FILE" | docker exec -i $CONTAINER_NAME psql -U $DB_USER -d postgres

echo "=== 복원 완료 ==="

# 임시 파일 정리
rm -rf "$TEMP_DIR"
echo "임시 파일 정리 완료"

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