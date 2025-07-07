-- TimescaleDB 초기화 스크립트
-- 파일명: 01_init_timescaledb.sql
-- 목적: TimescaleDB 확장 설치 및 기본 권한 설정

-- TimescaleDB 확장 설치
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 확장 설치 확인
\dx

-- 사용자 권한 설정
GRANT ALL PRIVILEGES ON DATABASE stockeasy_collector TO collector_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO collector_user;

-- 기본 스키마 설정
ALTER DATABASE stockeasy_collector SET timezone TO 'Asia/Seoul';

-- TimescaleDB 설치 확인 쿼리
SELECT default_version, installed_version 
FROM pg_available_extensions 
WHERE name = 'timescaledb';

-- 초기화 완료 메시지
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'TimescaleDB 초기화가 완료되었습니다!';
    RAISE NOTICE '데이터베이스: stockeasy_collector';
    RAISE NOTICE '사용자: collector_user';
    RAISE NOTICE '타임존: Asia/Seoul';
    RAISE NOTICE '========================================';
END $$; 