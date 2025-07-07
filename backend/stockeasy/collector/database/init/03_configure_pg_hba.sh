#!/bin/bash
set -e

# pg_hba.conf 파일에 Docker 네트워크 접속 허용 규칙 추가
echo "host    all             all             172.19.0.0/16           md5" >> "$PGDATA/pg_hba.conf"

# 설정 다시 로드
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT pg_reload_conf();
EOSQL

echo "pg_hba.conf 설정이 완료되었습니다." 