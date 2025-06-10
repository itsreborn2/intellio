# TimescaleDB SQL 작성 가이드

## 📖 개요

TimescaleDB는 PostgreSQL 기반의 시계열 데이터베이스로, **압축**, **하이퍼테이블**, **시간 기반 파티셔닝** 등의 특유한 메커니즘을 가지고 있습니다. 이러한 특성을 고려하지 않은 SQL 작성은 심각한 성능 저하와 **튜플 압축 해제 오류**를 유발할 수 있습니다.

**이 요구사항들은 backend\stockeasy\collector 하위 폴더의 소스에만 적용해야합니다.**

## 🚨 핵심 위험 요소

### 1. 튜플 압축 해제 제한 오류
```
ConfigurationLimitExceededError: tuple decompression limit exceeded by operation
DETAIL: current limit: 100000, tuples decompressed: 444220
```

이 오류는 **압축된 과거 데이터를 대량으로 해제**할 때 발생합니다.

### 2. 함수 구분의 중요성

#### ✅ 안전한 함수들 (압축 상태에서도 작동)
- **일반 집계 함수**: `SUM()`, `AVG()`, `COUNT()`, `MAX()`, `MIN()`
- **TimescaleDB 전용**: `first()`, `last()`, `time_bucket()`
- **시간 범위 조건**: `>=`, `<`, `BETWEEN`
- **직접 비교**: `=`, `IN`, `!=`

#### ❌ 위험한 함수들 (압축 해제 유발)
- **날짜 함수**: `DATE()`, `EXTRACT()`, `DATE_TRUNC()` (WHERE절에서)
- **윈도우 함수**: `LAG()`, `LEAD()`, `ROW_NUMBER()`, `SUM() OVER()`
- **문자열 함수**: `LIKE '%pattern%'`, `UPPER()`, `LOWER()`
- **수학 함수**: 컬럼에 적용되는 `ABS()`, `ROUND()` 등

#### 🔑 핵심 규칙
**집계 함수 자체는 안전합니다!** 
**윈도우 함수(OVER)와 함께 사용될 때만 위험합니다!**

## ❌ 위험한 SQL 패턴들

### 1. 날짜/시간 함수 사용
```sql
-- ❌ 압축 해제 유발 - 절대 사용 금지
WHERE DATE(time) = '2025-06-10'
WHERE DATE_TRUNC('day', time) = '2025-06-10'
WHERE EXTRACT(year FROM time) = 2025
WHERE EXTRACT(month FROM time) = 6  
WHERE EXTRACT(day FROM time) = 10
WHERE TO_CHAR(time, 'YYYY-MM-DD') = '2025-06-10'
WHERE DATE_PART('hour', time) = 9

-- ❌ 타입 변환도 위험
WHERE CAST(time AS DATE) = '2025-06-10'
WHERE time::DATE = '2025-06-10'
```

### 2. 컬럼에 함수 적용
```sql
-- ❌ 압축 해제 유발
WHERE ABS(price) > 1000
WHERE ROUND(price, 2) = 100.50
WHERE FLOOR(volume) > 1000000
WHERE UPPER(symbol) = 'SAMSUNG'
WHERE LOWER(name) LIKE '%삼성%'
```

### 3. 패턴 매칭 함수
```sql
-- ❌ 압축 해제 유발
WHERE symbol LIKE '%005%'
WHERE symbol ~ '^[0-9]+$'  -- 정규식
WHERE name ILIKE '%삼성%'
```

### 4. 조건 함수들
```sql
-- ❌ 압축 해제 유발
WHERE CASE WHEN price > 1000 THEN 'HIGH' ELSE 'LOW' END = 'HIGH'
WHERE COALESCE(adjusted_price, price) > 1000
WHERE NULLIF(volume, 0) IS NOT NULL
```

### 5. 윈도우 함수들 (매우 위험!)
```sql
-- ❌ 대량 압축 해제 유발 - 특히 위험
LAG(close, 1) OVER (ORDER BY time)
LEAD(price, 1) OVER (ORDER BY time)
ROW_NUMBER() OVER (ORDER BY time)
RANK() OVER (ORDER BY time)
DENSE_RANK() OVER (ORDER BY time)
FIRST_VALUE(close) OVER (ORDER BY time)
LAST_VALUE(close) OVER (ORDER BY time)

-- ❌ 윈도우 함수와 함께 사용되는 집계 함수들 (위험!)
SUM(volume) OVER (ORDER BY time ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)
AVG(close) OVER (ORDER BY time ROWS BETWEEN 10 PRECEDING AND CURRENT ROW)
COUNT(*) OVER (PARTITION BY symbol ORDER BY time)
MAX(high) OVER (ORDER BY time ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING)
MIN(low) OVER (ORDER BY time ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING)

-- ❌ 파티션과 함께 사용해도 위험
LAG(close, 1) OVER (PARTITION BY symbol ORDER BY time)
SUM(volume) OVER (PARTITION BY symbol ORDER BY time)
```

**⚠️ 중요**: 위의 집계 함수들은 **윈도우 함수(OVER)와 함께 사용될 때만** 위험합니다!

### 6. 대량 DELETE 작업
```sql
-- ❌ 튜플 제한 오류 유발
DELETE FROM stock_prices 
WHERE DATE(time) = '2025-06-10' 
AND symbol = ANY(ARRAY['005930', '000660', ...]);  -- 대량 종목
```

## ✅ 안전한 SQL 패턴들

### 1. 시간 범위 조건 (가장 중요!)
```sql
-- ✅ 인덱스 활용, 압축 유지
-- 특정 날짜
WHERE time >= '2025-06-10 00:00:00' 
  AND time < '2025-06-11 00:00:00'

-- 특정 월
WHERE time >= '2025-06-01 00:00:00'
  AND time < '2025-07-01 00:00:00'

-- 특정 시간대
WHERE time >= '2025-06-10 09:00:00'
  AND time < '2025-06-10 10:00:00'

-- 최근 N일
WHERE time >= NOW() - INTERVAL '7 days'

-- 특정 기간
WHERE time BETWEEN '2025-06-01' AND '2025-06-30'
```

### 2. 직접 값 비교
```sql
-- ✅ 압축 유지
WHERE price BETWEEN 1000 AND 2000
WHERE volume > 1000000
WHERE symbol IN ('005930', '000660', '035420')
WHERE symbol = '005930'
WHERE interval_type = '1d'
```

### 3. 안전한 정렬과 제한
```sql
-- ✅ 시간 기반 정렬 (최적화됨)
ORDER BY time DESC
ORDER BY time ASC

-- ✅ 적절한 LIMIT 사용
SELECT * FROM stock_prices 
WHERE symbol = '005930' 
  AND time >= '2025-06-01'
ORDER BY time DESC 
LIMIT 100;
```

### 3-1. 안전한 집계 함수 사용 (매우 중요!)
```sql
-- ✅ 일반 집계 함수는 안전하게 사용 가능
-- 시간 범위가 있으면 압축 상태에서도 효율적으로 집계
SELECT 
    symbol,
    COUNT(*) as total_records,
    SUM(volume) as total_volume,
    AVG(close) as avg_price,
    MAX(high) as max_price,
    MIN(low) as min_price,
    STDDEV(close) as price_volatility
FROM stock_prices 
WHERE symbol = '005930'
  AND time >= '2025-06-01'
  AND time < '2025-07-01'
GROUP BY symbol;

-- ✅ 시간별 집계 (TimescaleDB 최적화)
SELECT 
    time_bucket('1 day', time) as day,
    symbol,
    first(open, time) as day_open,
    last(close, time) as day_close,
    max(high) as day_high,
    min(low) as day_low,
    sum(volume) as day_volume
FROM stock_prices 
WHERE time >= '2025-06-01'
  AND time < '2025-07-01'
  AND symbol IN ('005930', '000660')
GROUP BY day, symbol
ORDER BY day DESC;

-- ✅ 여러 종목 비교 집계
SELECT 
    symbol,
    DATE_TRUNC('month', time) as month,
    AVG(close) as avg_monthly_price,
    SUM(volume) as monthly_volume,
    COUNT(*) as trading_days
FROM stock_prices 
WHERE time >= '2025-01-01'
  AND time < '2025-07-01'
  AND interval_type = '1d'
GROUP BY symbol, month
ORDER BY symbol, month;
```

### 4. 윈도우 함수 대안 방법
```sql
-- ❌ 위험한 LAG() 사용
SELECT 
    time, symbol, close,
    LAG(close, 1) OVER (ORDER BY time) as prev_close
FROM stock_prices 
WHERE symbol = '005930'
  AND time >= '2025-06-01'
ORDER BY time;

-- ✅ 안전한 대안: SELF JOIN 사용 (제한된 범위에서)
SELECT 
    curr.time, curr.symbol, curr.close,
    prev.close as prev_close
FROM stock_prices curr
LEFT JOIN stock_prices prev ON (
    prev.symbol = curr.symbol 
    AND prev.time = (
        SELECT MAX(time) 
        FROM stock_prices 
        WHERE symbol = curr.symbol 
          AND time < curr.time
          AND time >= '2025-06-01'  -- 범위 제한 필수
    )
)
WHERE curr.symbol = '005930'
  AND curr.time >= '2025-06-01'
  AND curr.time <= '2025-06-02'  -- 단기간만 조회
ORDER BY curr.time;

-- ✅ 더 안전한 방법: 애플리케이션에서 처리
-- 1. 데이터를 시간순으로 조회
SELECT time, symbol, close, volume
FROM stock_prices 
WHERE symbol = '005930'
  AND time >= '2025-06-01'
  AND time <= '2025-06-02'
ORDER BY time;

-- 2. 애플리케이션 코드에서 이전 값 계산
```

### 5. TimescaleDB 전용 최적화 함수들
```sql
-- ✅ TimescaleDB 전용 함수들 (압축 상태에서도 최적화됨)
-- 시간 버킷 집계
SELECT 
    time_bucket('1 hour', time) as hour,
    symbol,
    first(close, time) as first_price,
    last(close, time) as last_price,
    max(high) as max_price,
    min(low) as min_price
FROM stock_prices 
WHERE time >= '2025-06-10'
  AND time < '2025-06-11'
GROUP BY hour, symbol;

-- ✅ 연속 집계 (Continuous Aggregates) 활용
-- 미리 계산된 집계 테이블 사용
SELECT * FROM daily_stock_summary 
WHERE time >= '2025-06-01'
  AND symbol = '005930';

-- ✅ 하이퍼함수 사용
SELECT 
    symbol,
    stats_agg(close) as price_stats,
    approx_percentile(0.5, percentile_agg(close)) as median_price
FROM stock_prices 
WHERE time >= '2025-06-01'
  AND time < '2025-07-01'
GROUP BY symbol;

-- ✅ 압축 친화적 시간 범위 집계
SELECT 
    time_bucket_gapfill('1 day', time) as day,
    symbol,
    locf(avg(close)) as avg_close  -- 결측값 채우기
FROM stock_prices 
WHERE time >= '2025-06-01'
  AND time < '2025-07-01'
  AND symbol = '005930'
GROUP BY day, symbol
ORDER BY day;
```

## 🏗️ 데이터 수정 작업 패턴

### 1. UPSERT 사용 (DELETE 대신)
```sql
-- ✅ 안전한 당일 데이터 업데이트
INSERT INTO stock_prices (time, symbol, interval_type, open, high, low, close, volume)
VALUES ('2025-06-10 00:00:00', '005930', '1d', 70000, 71000, 69000, 70500, 1000000)
ON CONFLICT (time, symbol, interval_type) 
DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    -- 수정주가 정보는 기존 값 보존
    adjusted_price_type = COALESCE(stock_prices.adjusted_price_type, EXCLUDED.adjusted_price_type),
    adjustment_ratio = COALESCE(stock_prices.adjustment_ratio, EXCLUDED.adjustment_ratio),
    created_at = EXCLUDED.created_at;
```

### 2. 배치 크기 제한
```sql
-- ✅ 작은 배치로 처리 (50개 이하 권장)
WITH batch_symbols AS (
    SELECT unnest(ARRAY['005930', '000660', '035420']) as symbol
)
INSERT INTO stock_prices (...)
SELECT ... FROM batch_symbols ...;
```

## 📊 성능 최적화 전략

### 1. 계산 컬럼 활용
```sql
-- 자주 사용하는 계산은 미리 저장
ALTER TABLE stock_prices ADD COLUMN 
    trade_date DATE GENERATED ALWAYS AS (DATE(time)) STORED;

-- 인덱스 생성
CREATE INDEX idx_stock_prices_trade_date ON stock_prices (trade_date);

-- 빠른 조회
SELECT * FROM stock_prices 
WHERE trade_date = '2025-06-10'
  AND symbol = '005930';
```

### 2. 적절한 인덱스 전략
```sql
-- ✅ 복합 인덱스 (시간 + 종목)
CREATE INDEX idx_stock_prices_time_symbol 
ON stock_prices (time DESC, symbol);

-- ✅ 부분 인덱스 (조건부)
CREATE INDEX idx_stock_prices_recent 
ON stock_prices (symbol, time DESC) 
WHERE time >= '2025-01-01';
```

### 3. 압축 설정 최적화
```sql
-- 압축 정책 설정 (7일 후 압축)
SELECT add_compression_policy('stock_prices', INTERVAL '7 days');

-- 압축 상태 확인
SELECT * FROM timescaledb_information.chunks 
WHERE hypertable_name = 'stock_prices' 
  AND is_compressed = true;
```

## 🔍 실제 사용 예제

### 1. 당일 차트 데이터 조회
```sql
-- ✅ 올바른 방법
SELECT symbol, time, open, high, low, close, volume
FROM stock_prices 
WHERE time >= CURRENT_DATE 
  AND time < CURRENT_DATE + INTERVAL '1 day'
  AND interval_type = '1d'
  AND symbol IN ('005930', '000660', '035420')
ORDER BY symbol, time;
```

### 2. 최근 일주일 데이터 집계
```sql
-- ✅ 시간 범위 + 집계
SELECT 
    symbol,
    DATE_TRUNC('day', time) as trade_date,
    first(open, time) as day_open,
    max(high) as day_high,
    min(low) as day_low,
    last(close, time) as day_close,
    sum(volume) as day_volume
FROM stock_prices 
WHERE time >= NOW() - INTERVAL '7 days'
  AND interval_type = '1m'
  AND symbol = '005930'
GROUP BY symbol, DATE_TRUNC('day', time)
ORDER BY trade_date;
```

### 3. 수정주가 정보 조회
```sql
-- ✅ 수정주가가 있는 종목만 조회
SELECT symbol, time, close, adjusted_price_type, adjustment_ratio
FROM stock_prices 
WHERE time >= '2025-06-01'
  AND time < '2025-07-01'
  AND interval_type = '1d'
  AND adjusted_price_type IS NOT NULL
ORDER BY time DESC, symbol;
```

### 4. 변동률 계산 - 안전한 방법
```sql
-- ❌ 위험한 방법 (실제 오류 발생한 쿼리)
WITH recent_data AS (
    SELECT
        time, symbol, interval_type, close, volume,
        LAG(close, 1) OVER (ORDER BY time) as prev_close,
        LAG(volume, 1) OVER (ORDER BY time) as prev_volume
    FROM stock_prices
    WHERE symbol = '000720'
      AND time >= '2023-06-21'  -- 2년 전 데이터까지!
      AND close IS NOT NULL
    ORDER BY time
)
UPDATE stock_prices SET ...  -- 444,220개 튜플 압축 해제!

-- ✅ 안전한 방법 1: 최근 데이터만 처리
WITH recent_data AS (
    SELECT 
        time, symbol, close, volume,
        LAG(close, 1) OVER (PARTITION BY symbol ORDER BY time) as prev_close
    FROM stock_prices
    WHERE symbol = '000720'
      AND time >= CURRENT_DATE - INTERVAL '7 days'  -- 최근 7일만
      AND close IS NOT NULL
    ORDER BY time
)
UPDATE stock_prices 
SET previous_close_price = recent_data.prev_close
FROM recent_data
WHERE stock_prices.time = recent_data.time
  AND stock_prices.symbol = recent_data.symbol;

-- ✅ 안전한 방법 2: 배치 처리
-- 일자별로 나누어 처리
SELECT DISTINCT DATE(time) as trade_date
FROM stock_prices 
WHERE symbol = '000720'
  AND time >= '2025-06-01'
  AND previous_close_price IS NULL
ORDER BY trade_date
LIMIT 10;  -- 10일씩 처리

-- 각 일자별로 별도 처리
WITH daily_data AS (
    SELECT 
        time, symbol, close,
        LAG(close, 1) OVER (ORDER BY time) as prev_close
    FROM stock_prices
    WHERE symbol = '000720'
      AND DATE(time) = '2025-06-01'  -- 하루씩만
    ORDER BY time
)
UPDATE stock_prices 
SET previous_close_price = daily_data.prev_close
FROM daily_data
WHERE stock_prices.time = daily_data.time;
```

## ⚡ 성능 모니터링

### 1. 쿼리 성능 확인
```sql
-- 실행 계획 확인
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM stock_prices 
WHERE time >= '2025-06-10 00:00:00' 
  AND time < '2025-06-11 00:00:00'
  AND symbol = '005930';
```

### 2. 압축 상태 모니터링
```sql
-- 압축 통계 확인
SELECT 
    chunk_name,
    before_compression_bytes,
    after_compression_bytes,
    ROUND(
        (before_compression_bytes::float - after_compression_bytes::float) 
        / before_compression_bytes::float * 100, 2
    ) as compression_ratio_percent
FROM timescaledb_information.chunk_compression_stats;
```

## 🚫 절대 하지 말아야 할 것들

1. **DELETE + 대량 데이터**: 튜플 제한 오류 유발
2. **DATE() 함수**: 모든 압축 데이터 해제
3. **윈도우 함수 (LAG, LEAD 등)**: 대량 압축 해제 유발
4. **LIKE '%pattern%'**: 전체 테이블 스캔
5. **컬럼에 함수 적용**: 인덱스 무력화
6. **장기간 + 윈도우 함수**: 특히 위험한 조합
7. **대량 UPDATE**: 압축 무효화

## ✅ 권장 사항

1. **항상 시간 범위 조건 사용**
2. **UPSERT 방식으로 데이터 수정**
3. **배치 크기 50개 이하 유지**
4. **계산 컬럼 활용**
5. **쿼리 실행 계획 정기 점검**

## 📝 체크리스트

쿼리 작성 전 반드시 확인:

- [ ] 시간 컬럼에 함수를 사용했는가?
- [ ] DATE(), EXTRACT() 등의 함수가 있는가?
- [ ] **LAG(), LEAD() 등 윈도우 함수를 사용했는가?**
- [ ] **윈도우 함수 사용 시 시간 범위를 제한했는가?**
- [ ] 범위 조건 (>=, <) 을 사용했는가?
- [ ] 배치 크기가 50개 이하인가?
- [ ] DELETE 대신 UPSERT를 사용했는가?
- [ ] **과거 2년 이상의 데이터를 대상으로 하는가?**

## 🔗 참고 자료

- [TimescaleDB 공식 문서 - Best Practices](https://docs.timescale.com/timescaledb/latest/how-to-guides/query-data/)
- [압축 관련 문서](https://docs.timescale.com/timescaledb/latest/how-to-guides/compression/)
- [하이퍼테이블 최적화](https://docs.timescale.com/timescaledb/latest/how-to-guides/hypertables/)

---

**⚠️ 중요**: 이 가이드를 따르지 않으면 시스템 성능 저하와 서비스 중단이 발생할 수 있습니다. 