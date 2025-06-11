# TimescaleDB 백업 스크립트 (Windows PowerShell)
# 개발 환경에서 프로덕션으로 데이터 이전용

# 에러 발생 시 스크립트 중단
$ErrorActionPreference = "Stop"

# 설정
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_DIR = "./backups/timescale"
$DB_NAME = "stockeasy_collector"
$DB_USER = "collector_user"
$BACKUP_FILE = "timescale_backup_$TIMESTAMP.sql"

Write-Host "=== TimescaleDB 백업 시작 ===" -ForegroundColor Green

# Docker Compose로 생성되는 실제 컨테이너 이름 확인
Write-Host "TimescaleDB 컨테이너 확인 중..." -ForegroundColor Yellow
$CONTAINER_NAME = docker-compose ps -q timescaledb | Select-Object -First 1

if ([string]::IsNullOrEmpty($CONTAINER_NAME)) {
    Write-Host "❌ TimescaleDB 컨테이너를 찾을 수 없습니다. 서비스가 실행 중인지 확인하세요." -ForegroundColor Red
    Write-Host "다음 명령어로 서비스를 시작하세요:" -ForegroundColor Yellow
    Write-Host "docker-compose up -d timescaledb" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ 컨테이너 확인: $CONTAINER_NAME" -ForegroundColor Green

# 백업 디렉토리 생성
if (!(Test-Path $BACKUP_DIR)) {
    New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
    Write-Host "✅ 백업 디렉토리 생성: $BACKUP_DIR" -ForegroundColor Green
}

Write-Host "타임스탬프: $TIMESTAMP" -ForegroundColor Cyan
Write-Host "백업 파일: $BACKUP_DIR/$BACKUP_FILE" -ForegroundColor Cyan

# 데이터베이스 백업 (스키마 + 데이터)
Write-Host "데이터베이스 백업 중..." -ForegroundColor Yellow
try {
    docker exec $CONTAINER_NAME pg_dump -U $DB_USER -d $DB_NAME --verbose --no-password --format=plain --clean --if-exists --create --encoding=UTF8 | Out-File -FilePath "$BACKUP_DIR/$BACKUP_FILE" -Encoding UTF8
    Write-Host "✅ 데이터베이스 백업 완료" -ForegroundColor Green
} catch {
    Write-Host "❌ 데이터베이스 백업 실패: $_" -ForegroundColor Red
    exit 1
}

# 백업 파일 압축
Write-Host "백업 파일 압축 중..." -ForegroundColor Yellow
try {
    # PowerShell에서 gzip 압축 (7-zip이 있으면 더 좋지만 기본 압축 사용)
    Compress-Archive -Path "$BACKUP_DIR/$BACKUP_FILE" -DestinationPath "$BACKUP_DIR/${BACKUP_FILE}.zip" -Force
    Remove-Item "$BACKUP_DIR/$BACKUP_FILE" -Force
    Write-Host "✅ 백업 파일 압축 완료" -ForegroundColor Green
} catch {
    Write-Host "❌ 백업 파일 압축 실패: $_" -ForegroundColor Red
    exit 1
}

Write-Host "=== 백업 완료 ===" -ForegroundColor Green
Write-Host "백업 파일: $BACKUP_DIR/${BACKUP_FILE}.zip" -ForegroundColor Cyan

# 백업 파일 크기 확인
if (Test-Path "$BACKUP_DIR/${BACKUP_FILE}.zip") {
    $fileSize = (Get-Item "$BACKUP_DIR/${BACKUP_FILE}.zip").Length
    $fileSizeKB = [math]::Round($fileSize / 1KB, 2)
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    
    if ($fileSizeMB -gt 1) {
        Write-Host "백업 크기: $fileSizeMB MB" -ForegroundColor Cyan
    } else {
        Write-Host "백업 크기: $fileSizeKB KB" -ForegroundColor Cyan
    }
}

# 백업 검증
Write-Host "=== 백업 검증 ===" -ForegroundColor Yellow
if (Test-Path "$BACKUP_DIR/${BACKUP_FILE}.zip") {
    Write-Host "✅ 백업 파일이 성공적으로 생성되었습니다." -ForegroundColor Green
    
    # ZIP 파일 내용 미리보기 (첫 몇 줄)
    try {
        $tempExtract = "$env:TEMP/timescale_preview_$TIMESTAMP"
        Expand-Archive -Path "$BACKUP_DIR/${BACKUP_FILE}.zip" -DestinationPath $tempExtract -Force
        $extractedFile = Get-ChildItem $tempExtract -Filter "*.sql" | Select-Object -First 1
        if ($extractedFile) {
            Write-Host "백업 파일 미리보기 (첫 10줄):" -ForegroundColor Yellow
            Get-Content $extractedFile.FullName -TotalCount 10 | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
        }
        Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host "미리보기 실패 (백업은 정상): $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ 백업 파일 생성에 실패했습니다." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "서버 복원을 위해 다음 명령어를 사용하세요:" -ForegroundColor Yellow
Write-Host "scp '$BACKUP_DIR/${BACKUP_FILE}.zip' user@server:/path/to/backups/" -ForegroundColor Cyan
Write-Host ""
Write-Host "또는 WinSCP, FileZilla 등의 GUI 도구를 사용하여 파일을 전송하세요." -ForegroundColor Yellow 