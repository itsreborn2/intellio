# TimescaleDB 서버 이주 가이드

이 문서는 Stock Data Collector의 TimescaleDB를 개발 환경에서 서버 환경으로 이주하는 과정을 설명합니다.

## 📋 사전 준비

### 1. 서버 환경 요구사항
- Docker 및 Docker Compose 설치
- 최소 4GB RAM (권장: 8GB 이상)
- 최소 50GB 디스크 공간 (데이터량에 따라 조정)
- 포트 5433, 6433 사용 가능

### 2. 필요한 파일들
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `backend/stockeasy/collector/.env.production`
- `backend/stockeasy/collector/database/init/` 디렉토리
- 백업 및 복원 스크립트

## 🔄 이주 프로세스

### 1단계: 개발 환경 데이터 백업 (Windows)

```powershell
# PowerShell에서 백업 실행
.\scripts\backup_timescale.ps1
```

**참고**: 만약 PowerShell 실행 정책 오류가 발생하면:
```powershell
# 실행 정책 변경 (관리자 권한 필요)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 또는 일회성 실행
PowerShell -ExecutionPolicy Bypass -File .\scripts\backup_timescale.ps1
```

### 2단계: 서버에 파일 업로드

```bash
# 프로젝트 파일을 서버에 업로드
rsync -av --exclude=node_modules --exclude=.git ./ user@server:/path/to/project/

# 백업 파일 업로드 (ZIP 형태)
scp backups/timescale/timescale_backup_*.sql.zip user@server:/path/to/project/backups/timescale/
```

**Windows에서 파일 전송 방법**:
- **WinSCP**: GUI 기반 SCP 클라이언트
- **FileZilla**: FTP/SFTP 클라이언트  
- **PowerShell SCP** (OpenSSH 설치된 경우):
  ```powershell
  scp .\backups\timescale\timescale_backup_*.zip user@server:/path/to/project/backups/timescale/
  ```

### 3단계: 서버에서 환경 설정

```bash
# 서버에 접속
ssh user@server

# 프로젝트 디렉토리로 이동
cd /path/to/project

# 환경 파일 권한 설정
chmod 600 backend/stockeasy/collector/.env.production
```

### 4단계: Docker 이미지 빌드

```bash
# base 이미지 빌드
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build base-image-prod

# stock-data-collector 이미지 빌드
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build stock-data-collector
```

### 5단계: TimescaleDB 서비스 시작

```bash
# TimescaleDB만 먼저 시작
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d timescaledb

# 서비스 상태 확인
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps timescaledb

# 로그 확인
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs timescaledb
```

### 6단계: PgBouncer 시작

```bash
# PgBouncer 시작
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d pgbouncer-timescale

# 연결 테스트
docker exec intellio-pgbouncer-timescale-1 pg_isready -h localhost -p 6432
```

### 7단계: 데이터 복원

```bash
# ZIP 파일 복원 스크립트 실행 권한 설정
chmod +x scripts/restore_timescale_from_zip.sh

# 데이터 복원 (ZIP 백업 파일 경로 지정)
./scripts/restore_timescale_from_zip.sh backups/timescale/timescale_backup_YYYYMMDD_HHMMSS.sql.zip
```

**참고**: gzip 백업 파일(.gz)이 있는 경우 기존 스크립트도 사용 가능:
```bash
chmod +x scripts/restore_timescale.sh
./scripts/restore_timescale.sh backups/timescale/timescale_backup_YYYYMMDD_HHMMSS.sql.gz
```

### 8단계: Stock Data Collector 시작

```bash
# 모든 의존성 서비스 시작
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d redis

# Stock Data Collector 시작
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d stock-data-collector

# 서비스 상태 확인
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps stock-data-collector

# 로그 확인
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f stock-data-collector
```

## 🔍 검증 및 모니터링

### 1. 연결 테스트

```bash
# 컨테이너 이름 확인
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# TimescaleDB 직접 연결 테스트
TIMESCALE_CONTAINER=$(docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps -q timescaledb)
docker exec $TIMESCALE_CONTAINER psql -U collector_user -d stockeasy_collector -c "SELECT version();"

# PgBouncer를 통한 연결 테스트
PGBOUNCER_CONTAINER=$(docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps -q pgbouncer-timescale)
docker exec $PGBOUNCER_CONTAINER psql -h localhost -p 6432 -U collector_user -d stockeasy_collector -c "SELECT count(*) FROM pg_tables;"
```

### 2. 데이터 검증

```bash
# 컨테이너 이름 가져오기
TIMESCALE_CONTAINER=$(docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps -q timescaledb)

# Hypertable 확인
docker exec $TIMESCALE_CONTAINER psql -U collector_user -d stockeasy_collector -c "
SELECT hypertable_name, schema_name, num_chunks 
FROM timescaledb_information.hypertables;
"

# 데이터 건수 확인
docker exec $TIMESCALE_CONTAINER psql -U collector_user -d stockeasy_collector -c "
SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del 
FROM pg_stat_user_tables 
ORDER BY n_tup_ins DESC;
"
```

### 3. API 엔드포인트 테스트

```bash
# 헬스체크
curl http://localhost:8001/health

# TimescaleDB 연결 상태 확인
curl http://localhost:8001/api/v1/timescale/health

# 스케줄러 상태 확인
curl http://localhost:8001/api/v1/scheduler/status
```

## 🔧 성능 최적화

### 1. TimescaleDB 설정 조정

프로덕션 환경에서는 다음 설정들을 서버 사양에 맞게 조정하세요:

```sql
-- 메모리 설정 (서버 RAM의 25%)
shared_buffers = 512MB          -- 2GB RAM 서버 기준
effective_cache_size = 2GB      -- 2GB RAM 서버 기준

-- 작업 메모리 설정
work_mem = 8MB
maintenance_work_mem = 128MB

-- 연결 설정
max_connections = 200
```

### 2. PgBouncer 설정 조정

```env
# 연결 풀 크기 조정 (서버 사양에 맞게)
MAX_CLIENT_CONN=200
DEFAULT_POOL_SIZE=30
```

### 3. Docker 리소스 제한

```yaml
# docker-compose.prod.yml에서 리소스 제한 설정
services:
  timescaledb:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "1.0"
        reservations:
          memory: 1G
          cpus: "0.5"
```

## 🚨 문제 해결

### 1. 연결 문제
```bash
# 포트 사용 확인
netstat -tulpn | grep :5433
netstat -tulpn | grep :6433

# 방화벽 설정 확인
sudo ufw status
```

### 2. 메모리 부족
```bash
# 시스템 메모리 확인
free -h

# Docker 메모리 사용량 확인
docker stats
```

### 3. 디스크 공간 부족
```bash
# 디스크 사용량 확인
df -h

# Docker 볼륨 정리
docker volume prune
```

## 📊 모니터링 설정

### 1. 로그 모니터링
```bash
# 모든 서비스 로그 확인
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# 특정 서비스 로그만 확인
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f timescaledb
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f stock-data-collector
```

### 2. 성능 모니터링
```bash
# 컨테이너 이름 가져오기
TIMESCALE_CONTAINER=$(docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps -q timescaledb)

# TimescaleDB 성능 통계
docker exec $TIMESCALE_CONTAINER psql -U collector_user -d stockeasy_collector -c "
SELECT schemaname, tablename, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch 
FROM pg_stat_user_tables 
ORDER BY seq_scan DESC;
"

# 연결 통계
docker exec $TIMESCALE_CONTAINER psql -U collector_user -d stockeasy_collector -c "
SELECT datname, numbackends, xact_commit, xact_rollback, blks_read, blks_hit 
FROM pg_stat_database 
WHERE datname = 'stockeasy_collector';
"
```

## 🔄 백업 및 복구 전략

### 1. 정기 백업 설정
```bash
# crontab 설정 (매일 새벽 2시 백업)
0 2 * * * /path/to/project/scripts/backup_timescale.sh >> /var/log/timescale_backup.log 2>&1
```

### 2. 백업 파일 관리
```bash
# 오래된 백업 파일 정리 (30일 이상된 파일 삭제)
find backups/timescale/ -name "*.sql.gz" -mtime +30 -delete
```

## 📝 체크리스트

배포 완료 후 다음 항목들을 확인하세요:

- [ ] TimescaleDB 서비스 정상 실행
- [ ] PgBouncer 연결 풀 정상 작동
- [ ] Stock Data Collector 서비스 정상 시작
- [ ] 스케줄러 작업 정상 등록
- [ ] API 엔드포인트 응답 정상
- [ ] 데이터 수집 작업 정상 실행
- [ ] 로그 파일 정상 생성
- [ ] 백업 스크립트 정상 작동
- [ ] 모니터링 시스템 설정 완료

## 🔗 관련 문서

- [TimescaleDB 공식 문서](https://docs.timescale.com/)
- [PgBouncer 설정 가이드](https://www.pgbouncer.org/config.html)
- [Docker Compose 프로덕션 가이드](https://docs.docker.com/compose/production/) 