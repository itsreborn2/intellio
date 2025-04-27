# PostgreSQL 데이터베이스 마이그레이션 가이드

이 문서는 로컬 개발 환경에서 웹서버 프로덕션 환경으로 PostgreSQL 데이터베이스의 특정 테이블을 안전하게 마이그레이션하는 방법을 설명합니다.

## 환경 정보

### 로컬 개발 환경
- PostgreSQL 컨테이너명: `intellio-postgres-1` (주의: 실제 컨테이너명은 postgres임)
- 데이터베이스명: `intellio_dev`
- 사용자명: `intellio_user_dev`
- 스키마: `stockeasy`

### 웹서버 프로덕션 환경
- PostgreSQL 컨테이너명: `intellio-postgres-1`
- 데이터베이스명: `intellio`
- 사용자명: `intellio_user`
- 스키마: `stockeasy`

## 마이그레이션 대상 테이블
다음 테이블들만 마이그레이션합니다:
- stockeasy.companies
- stockeasy.financial_item_mappings
- stockeasy.financial_item_raw_mappings
- stockeasy.financial_reports
- stockeasy.income_statement_data
- stockeasy.summary_financial_data
- stockeasy.equity_change_data
- stockeasy.cash_flow_data
- stockeasy.balance_sheet_data

## 데이터베이스 마이그레이션 단계

### 1. 로컬 환경에서 특정 테이블 덤프 생성

PowerShell에서는 다음과 같이 명령어를 실행합니다:

```powershell
# 덤프 디렉토리 생성 (필요한 경우)
mkdir -p db_dumps

# PowerShell에서 여러 줄 명령어 실행 (백틱 사용)
docker exec -it intellio-postgres-1 pg_dump -U intellio_user_dev -d intellio_dev -F c `
-t stockeasy.companies `
-t stockeasy.financial_item_mappings `
-t stockeasy.financial_item_raw_mappings `
-t stockeasy.financial_reports `
-t stockeasy.income_statement_data `
-t stockeasy.summary_financial_data `
-t stockeasy.equity_change_data `
-t stockeasy.cash_flow_data `
-t stockeasy.balance_sheet_data `
-f /tmp/stockeasy_backup.dump
```

### 2. 덤프 파일을 로컬 시스템으로 복사

```powershell
docker cp intellio-postgres-1:/tmp/stockeasy_backup.dump ./db_dumps/stockeasy_backup.dump
```

### 3. 덤프 파일을 웹서버로 전송

```powershell
# SCP를 사용하여 로컬 파일을 웹서버로 전송 (SSH 키 사용)
scp -i C:\Users\blues\id_intellio ./db_dumps/stockeasy_backup.dump intellio.korea@128.199.172.222:/tmp/
```

### 4. 웹서버에서 덤프 파일을 Docker 컨테이너로 복사

```powershell
# 웹서버에서 실행 (SSH로 접속 후)
ssh -i C:\Users\blues\id_intellio intellio.korea@128.199.172.222
docker cp /tmp/stockeasy_backup.dump intellio-postgres-1:/tmp/
```

### 5. 웹서버에서 데이터베이스 복원

```powershell
# 웹서버의 Docker 컨테이너에서 실행
docker exec -it intellio-postgres-1 pg_restore -U intellio_user -d intellio `
--no-owner --no-acl --clean --if-exists /tmp/stockeasy_backup.dump
```

## 한 번에 실행하는 방법 (리눅스/Mac 환경)

리눅스나 Mac 환경에서는 다음과 같이 파이프로 직접 연결할 수 있습니다:

```bash
docker exec -it intellio-postgres-1 pg_dump -U intellio_user_dev -d intellio_dev -F c \
-t stockeasy.companies \
-t stockeasy.financial_item_mappings \
-t stockeasy.financial_item_raw_mappings \
-t stockeasy.financial_reports \
-t stockeasy.income_statement_data \
-t stockeasy.summary_financial_data \
-t stockeasy.equity_change_data \
-t stockeasy.cash_flow_data \
-t stockeasy.balance_sheet_data | \
ssh -i ~/path/to/ssh_key [사용자명]@[웹서버주소] "docker exec -i intellio-postgres-1 pg_restore -U intellio_user -d intellio --no-owner --no-acl --clean --if-exists"
```

## 주의사항

- 이 방법은 대상 테이블이 이미 존재하면 덮어씁니다(`--clean --if-exists` 옵션).
- 복원 중 외래 키 제약조건으로 인한 오류가 발생하면 `--disable-triggers` 옵션을 추가할 수 있지만, 데이터 무결성에 영향을 줄 수 있으므로 신중하게 사용하세요.
- 마이그레이션 전에 중요한 데이터는 항상 백업하세요.
- 가능하면 트래픽이 적은 시간에 마이그레이션을 수행하세요.
- 대상 테이블 외에 다른 stockeasy 스키마의 데이터(예: `stockeasy_chat_session`, `stockeasy_chat_messages`)는 건드리지 않습니다. 