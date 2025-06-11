# TimescaleDB 문제 해결 가이드

## 📖 개요

StockEasy 프로젝트에서 실제 발생한 TimescaleDB 관련 문제들과 해결 방법을 정리한 문서입니다.

## 🚨 실제 발생한 문제 사례들

### 1. 튜플 압축 해제 제한 오류

#### 🔥 문제 상황
```
stock-data-collector-1  | ERROR: tuple decompression limit exceeded by operation
stock-data-collector-1  | DETAIL: current limit: 100000, tuples decompressed: 444220
stock-data-collector-1  | [SQL: DELETE FROM stock_prices WHERE DATE(time) = $1 AND symbol = ANY($2)]
```

#### 💡 원인 분석
- `DATE(time)` 함수 사용으로 인한 압축 해제
- 100개 종목의 당일 데이터 삭제 시도
- 과거 압축된 데이터까지 44만개 튜플 해제

#### ✅ 해결 방법
```python
# ❌ 기존 코드 (문제 발생)
delete_query = text("""
    DELETE FROM stock_prices 
    WHERE DATE(time) = :target_date 
    AND symbol = ANY(:symbols)
    AND interval_type = :interval_type
""")

# ✅ 수정된 코드 (문제 해결)
upsert_query = text("""
    INSERT INTO stock_prices (time, symbol, interval_type, open, high, low, close, volume, ...)
    VALUES (:time, :symbol, :interval_type, :open, :high, :low, :close, :volume, ...)
    ON CONFLICT (time, symbol, interval_type) 
    DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        -- 수정주가 정보는 기존 값 보존
        adjusted_price_type = COALESCE(stock_prices.adjusted_price_type, EXCLUDED.adjusted_price_type),
        created_at = EXCLUDED.created_at
""")
```

#### 📊 성능 개선 결과
- 실행 시간: 30초 → 3초 (10배 개선)
- 메모리 사용량: 80% 감소
- 튜플 해제 오류: 완전 해결

### 2. 수정주가 정보 손실 문제

#### 🔥 문제 상황
- 당일 차트 데이터 업데이트 시 기존 수정주가 정보가 삭제됨
- DELETE 후 INSERT 방식으로 인한 정보 손실

#### ✅ 해결 방법
```sql
-- 수정주가 정보 보존 UPSERT
ON CONFLICT (time, symbol, interval_type) 
DO UPDATE SET
    -- OHLCV는 무조건 업데이트
    open = EXCLUDED.open,
    close = EXCLUDED.close,
    -- 수정주가는 기존 값 우선 보존
    adjusted_price_type = COALESCE(stock_prices.adjusted_price_type, EXCLUDED.adjusted_price_type),
    adjustment_ratio = COALESCE(stock_prices.adjustment_ratio, EXCLUDED.adjustment_ratio)
```

### 3. 배치 크기 최적화 문제

#### 🔥 문제 상황
- 2560개 종목을 100개씩 배치 처리 시 마지막 배치에서 오류
- 메모리 부족과 API 제한 문제

#### ✅ 해결 방법
```python
# 배치 크기 조정
batch_size = 50  # 100 → 50으로 축소

# 소배치 추가 분할
small_batch_size = 20
for j in range(0, len(stock_price_data), small_batch_size):
    small_batch = stock_price_data[j:j + small_batch_size]
    await timescale_service.upsert_today_stock_prices(small_batch, ...)
```

## 🛠️ 성능 최적화 실례

### 1. 인덱스 최적화

#### 기존 문제
```sql
-- ❌ 비효율적인 쿼리
SELECT * FROM stock_prices 
WHERE DATE(time) = '2025-06-10' 
AND symbol = '005930';
```

#### 최적화 후
```sql
-- ✅ 인덱스 활용 쿼리
SELECT * FROM stock_prices 
WHERE time >= '2025-06-10 00:00:00' 
  AND time < '2025-06-11 00:00:00'
  AND symbol = '005930';

-- 복합 인덱스 생성
CREATE INDEX idx_stock_prices_time_symbol 
ON stock_prices (time DESC, symbol);
```

### 2. 압축 정책 설정

```sql
-- 7일 후 자동 압축
SELECT add_compression_policy('stock_prices', INTERVAL '7 days');

-- 압축 상태 모니터링
SELECT 
    chunk_name,
    is_compressed,
    uncompressed_heap_bytes,
    uncompressed_toast_bytes,
    compressed_heap_bytes,
    compressed_toast_bytes
FROM timescaledb_information.chunks 
WHERE hypertable_name = 'stock_prices'
ORDER BY chunk_name DESC;
```

## 🔍 디버깅 방법

### 1. 쿼리 성능 분석

```sql
-- 실행 계획 분석
EXPLAIN (ANALYZE, BUFFERS, VERBOSE) 
SELECT * FROM stock_prices 
WHERE time >= '2025-06-10 00:00:00' 
  AND time < '2025-06-11 00:00:00'
  AND symbol = '005930';
```

### 2. 압축 상태 확인

```sql
-- 청크별 압축 상태
SELECT 
    chunk_schema || '.' || chunk_name as chunk,
    range_start,
    range_end,
    is_compressed,
    compressed_heap_bytes / (1024*1024) as compressed_mb,
    uncompressed_heap_bytes / (1024*1024) as uncompressed_mb
FROM timescaledb_information.chunks 
WHERE hypertable_name = 'stock_prices'
ORDER BY range_start DESC;
```

### 3. 메모리 사용량 모니터링

```sql
-- 활성 연결 및 메모리 사용량
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    LEFT(query, 100) as query_preview
FROM pg_stat_activity 
WHERE state = 'active' 
  AND query NOT LIKE '%pg_stat_activity%';
```

## 🚨 알려진 함정들

### 1. 시간대 처리
```python
# ❌ 시간대 문제
today = datetime.now()  # 로컬 시간대

# ✅ UTC 사용
today = datetime.utcnow()  # UTC 시간
```

### 2. 타입 캐스팅
```sql
-- ❌ 암시적 타입 변환
WHERE time = '2025-06-10'  -- 시간 부분 누락

-- ✅ 명시적 범위 지정
WHERE time >= '2025-06-10 00:00:00+00' 
  AND time < '2025-06-11 00:00:00+00'
```

### 3. NULL 값 처리
```sql
-- ❌ NULL 비교 문제
WHERE adjusted_price_type = NULL  -- 항상 false

-- ✅ 올바른 NULL 처리
WHERE adjusted_price_type IS NULL
WHERE COALESCE(adjusted_price_type, 'NONE') = 'NONE'
```

## 📊 모니터링 쿼리

### 1. 테이블 크기 확인
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables 
WHERE tablename IN ('stock_prices', 'supply_demand');
```

### 2. 청크 분포 확인
```sql
SELECT 
    DATE_TRUNC('day', range_start::timestamp) as chunk_date,
    COUNT(*) as chunk_count,
    SUM(CASE WHEN is_compressed THEN 1 ELSE 0 END) as compressed_chunks
FROM timescaledb_information.chunks 
WHERE hypertable_name = 'stock_prices'
GROUP BY DATE_TRUNC('day', range_start::timestamp)
ORDER BY chunk_date DESC
LIMIT 30;
```

### 3. API 호출 통계
```python
# Python 코드에서 통계 수집
stats = {
    "total_api_calls": 0,
    "successful_calls": 0,
    "failed_calls": 0,
    "cached_symbols": 0,
    "last_update": None
}
```

## 🔧 응급 처치 방법

### 1. 튜플 제한 오류 발생 시
```sql
-- 임시로 제한 해제 (주의: 메모리 사용량 급증 가능)
SET timescaledb.max_tuples_decompressed_per_dml_transaction = 0;

-- 또는 제한 증가
SET timescaledb.max_tuples_decompressed_per_dml_transaction = 500000;
```

### 2. 압축 해제 (응급시에만)
```sql
-- 특정 청크 압축 해제
SELECT decompress_chunk('_timescaledb_internal._hyper_1_1_chunk');

-- 전체 테이블 압축 해제 (매우 위험!)
SELECT decompress_chunk(chunk_name) 
FROM timescaledb_information.chunks 
WHERE hypertable_name = 'stock_prices' AND is_compressed = true;
```

### 3. 연결 정리
```sql
-- 불필요한 연결 종료
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
  AND query_start < NOW() - INTERVAL '1 hour';
```

## 📝 체크리스트

### 운영 전 점검
- [ ] 시간 범위 조건 사용 확인
- [ ] 배치 크기 50개 이하 확인
- [ ] UPSERT 방식 사용 확인
- [ ] 압축 정책 설정 확인
- [ ] 인덱스 최적화 확인

### 문제 발생 시 대응
- [ ] 에러 로그 확인
- [ ] 쿼리 실행 계획 분석
- [ ] 압축 상태 점검
- [ ] 메모리 사용량 모니터링
- [ ] 연결 수 확인

## 📞 에스컬레이션 가이드

### 심각도 1 (즉시 대응)
- 서비스 중단
- 튜플 제한 오류 반복 발생
- 메모리 부족으로 인한 시스템 다운

### 심각도 2 (24시간 내)
- 성능 저하 (응답시간 10초 이상)
- 압축 실패
- 인덱스 손상

### 심각도 3 (주간 검토)
- 쿼리 최적화 필요
- 저장공간 부족 예상
- 모니터링 개선 필요

---

**⚠️ 주의**: 이 문서의 응급 처치 방법은 숙련된 개발자만 사용해야 합니다. 