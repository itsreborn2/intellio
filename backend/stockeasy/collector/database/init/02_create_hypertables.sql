-- TimescaleDB 하이퍼테이블 생성 및 최적화 설정
-- 이 스크립트는 01_init_timescaledb.sql 실행 후에 실행됩니다.

-- ========================================
-- 기본 테이블 생성 (SQLAlchemy로 생성될 예정이지만 확실히 하기 위해)
-- ========================================

-- 주가 데이터 테이블
CREATE TABLE IF NOT EXISTS stock_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    interval_type VARCHAR(10) NOT NULL DEFAULT '1m',
    open NUMERIC(12,2),
    high NUMERIC(12,2),
    low NUMERIC(12,2),
    close NUMERIC(12,2),
    volume BIGINT,
    trading_value BIGINT,
    change_amount NUMERIC(12,2),
    change_rate NUMERIC(8,4),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (time, symbol, interval_type)
);

-- 수급 데이터 테이블
CREATE TABLE IF NOT EXISTS supply_demand (
    date TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    institution_amount BIGINT,
    foreign_amount BIGINT,
    individual_amount BIGINT,
    institution_volume BIGINT,
    foreign_volume BIGINT,
    individual_volume BIGINT,
    institution_cumulative BIGINT,
    foreign_cumulative BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, symbol)
);

-- 실시간 가격 테이블
CREATE TABLE IF NOT EXISTS realtime_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    volume BIGINT,
    bid_price NUMERIC(12,2),
    ask_price NUMERIC(12,2),
    bid_volume BIGINT,
    ask_volume BIGINT,
    change_amount NUMERIC(12,2),
    change_rate NUMERIC(8,4),
    trading_value BIGINT,
    accumulated_volume BIGINT,
    accumulated_value BIGINT,
    market_status VARCHAR(20),
    is_suspended BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (time, symbol)
);

-- 시장 지수 테이블
CREATE TABLE IF NOT EXISTS market_indices (
    time TIMESTAMPTZ NOT NULL,
    index_code VARCHAR(20) NOT NULL,
    index_value NUMERIC(12,2) NOT NULL,
    change_amount NUMERIC(12,2),
    change_rate NUMERIC(8,4),
    volume BIGINT,
    trading_value BIGINT,
    rise_count INTEGER,
    fall_count INTEGER,
    unchanged_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (time, index_code)
);

-- 거래 세션 테이블
CREATE TABLE IF NOT EXISTS trading_sessions (
    time TIMESTAMPTZ NOT NULL,
    market VARCHAR(20) NOT NULL,
    session_type VARCHAR(30) NOT NULL,
    session_status VARCHAR(20) NOT NULL,
    total_volume BIGINT,
    total_value BIGINT,
    listed_count INTEGER,
    trading_count INTEGER,
    meta_info TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (time, market)
);

-- ========================================
-- 하이퍼테이블 생성
-- ========================================

-- 주가 데이터 하이퍼테이블 (1일 청크)
SELECT create_hypertable(
    'stock_prices', 
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- 수급 데이터 하이퍼테이블 (7일 청크)
SELECT create_hypertable(
    'supply_demand', 
    'date',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- 실시간 가격 하이퍼테이블 (1시간 청크)
SELECT create_hypertable(
    'realtime_prices', 
    'time',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- 시장 지수 하이퍼테이블 (1일 청크)
SELECT create_hypertable(
    'market_indices', 
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- 거래 세션 하이퍼테이블 (1일 청크)
SELECT create_hypertable(
    'trading_sessions', 
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ========================================
-- 인덱스 생성
-- ========================================

-- 주가 데이터 인덱스
CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_time 
    ON stock_prices (symbol, time DESC, interval_type);
CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_interval 
    ON stock_prices (symbol, interval_type);
CREATE INDEX IF NOT EXISTS idx_stock_prices_time_desc 
    ON stock_prices (time DESC);

-- 수급 데이터 인덱스
CREATE INDEX IF NOT EXISTS idx_supply_demand_symbol_date 
    ON supply_demand (symbol, date DESC);
CREATE INDEX IF NOT EXISTS idx_supply_demand_date_desc 
    ON supply_demand (date DESC);

-- 실시간 가격 인덱스
CREATE INDEX IF NOT EXISTS idx_realtime_prices_symbol_time 
    ON realtime_prices (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_realtime_prices_time_desc 
    ON realtime_prices (time DESC);
CREATE INDEX IF NOT EXISTS idx_realtime_prices_market_status 
    ON realtime_prices (market_status) WHERE market_status IS NOT NULL;

-- 시장 지수 인덱스
CREATE INDEX IF NOT EXISTS idx_market_indices_index_time 
    ON market_indices (index_code, time DESC);
CREATE INDEX IF NOT EXISTS idx_market_indices_time_desc 
    ON market_indices (time DESC);

-- 거래 세션 인덱스
CREATE INDEX IF NOT EXISTS idx_trading_sessions_market_time 
    ON trading_sessions (market, time DESC);
CREATE INDEX IF NOT EXISTS idx_trading_sessions_session_type 
    ON trading_sessions (session_type);

-- ========================================
-- 연속 집계 (Continuous Aggregates) 생성
-- ========================================

-- 일봉 연속 집계 뷰
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_candles
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) as day,
    symbol,
    interval_type,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(trading_value) as trading_value,
    last(change_amount, time) as change_amount,
    last(change_rate, time) as change_rate
FROM stock_prices
WHERE interval_type = '1m'  -- 1분봉에서만 일봉 생성
GROUP BY day, symbol, interval_type;

-- 시간별 실시간 가격 집계 뷰
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_realtime_summary
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) as hour,
    symbol,
    first(price, time) as open_price,
    max(price) as high_price,
    min(price) as low_price,
    last(price, time) as close_price,
    sum(volume) as total_volume,
    sum(trading_value) as total_trading_value,
    count(*) as tick_count
FROM realtime_prices
GROUP BY hour, symbol;

-- ========================================
-- 압축 설정
-- ========================================

-- 주가 데이터 압축 설정 (30일 후)
ALTER TABLE stock_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, interval_type',
    timescaledb.compress_orderby = 'time DESC'
);

-- 수급 데이터 압축 설정 (90일 후)
ALTER TABLE supply_demand SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'date DESC'
);

-- 실시간 가격 압축 설정 (7일 후)
ALTER TABLE realtime_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);

-- 시장 지수 압축 설정 (30일 후)
ALTER TABLE market_indices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'index_code',
    timescaledb.compress_orderby = 'time DESC'
);

-- 거래 세션 압축 설정 (90일 후)
ALTER TABLE trading_sessions SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'market',
    timescaledb.compress_orderby = 'time DESC'
);

-- ========================================
-- 압축 정책 추가
-- ========================================

-- 주가 데이터 압축 정책 (30일 후 압축)
SELECT add_compression_policy('stock_prices', INTERVAL '30 days');

-- 수급 데이터 압축 정책 (90일 후 압축)
SELECT add_compression_policy('supply_demand', INTERVAL '90 days');

-- 실시간 가격 압축 정책 (7일 후 압축)
SELECT add_compression_policy('realtime_prices', INTERVAL '7 days');

-- 시장 지수 압축 정책 (30일 후 압축)
SELECT add_compression_policy('market_indices', INTERVAL '30 days');

-- 거래 세션 압축 정책 (90일 후 압축)
SELECT add_compression_policy('trading_sessions', INTERVAL '90 days');

-- ========================================
-- 데이터 보관 정책
-- ========================================

-- 실시간 가격은 30일만 보관 (나머지는 압축된 시간별 집계 사용)
SELECT add_retention_policy('realtime_prices', INTERVAL '30 days');

-- 1분봉 데이터는 1년 보관
SELECT add_retention_policy('stock_prices', INTERVAL '1 year');

-- ========================================
-- 연속 집계 자동 갱신 정책
-- ========================================

-- 일봉 연속 집계 자동 갱신 (1시간마다)
SELECT add_continuous_aggregate_policy('daily_candles',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- 시간별 실시간 집계 자동 갱신 (15분마다)
SELECT add_continuous_aggregate_policy('hourly_realtime_summary',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

-- ========================================
-- 유용한 함수 생성
-- ========================================

-- 테이블 압축률 확인 함수
CREATE OR REPLACE FUNCTION get_compression_stats()
RETURNS TABLE(
    table_name TEXT,
    total_chunks INTEGER,
    compressed_chunks INTEGER,
    compression_ratio NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        format('%I.%I', schema_name, table_name)::TEXT,
        total_chunks::INTEGER,
        number_compressed_chunks::INTEGER,
        CASE 
            WHEN total_chunks > 0 
            THEN ROUND((number_compressed_chunks::NUMERIC / total_chunks::NUMERIC) * 100, 2)
            ELSE 0::NUMERIC
        END as compression_ratio
    FROM timescaledb_information.hypertables h
    LEFT JOIN timescaledb_information.chunks c ON h.hypertable_name = c.hypertable_name
    WHERE h.schema_name = 'public'
    GROUP BY h.schema_name, h.table_name, h.total_chunks, h.number_compressed_chunks;
END;
$$ LANGUAGE plpgsql;

-- 하이퍼테이블 상태 확인 함수
CREATE OR REPLACE FUNCTION get_hypertable_info()
RETURNS TABLE(
    table_name TEXT,
    table_size TEXT,
    total_chunks INTEGER,
    compressed_chunks INTEGER,
    compression_ratio TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        h.table_name::TEXT,
        pg_size_pretty(pg_total_relation_size(format('%I.%I', h.schema_name, h.table_name)::regclass))::TEXT as table_size,
        h.total_chunks::INTEGER,
        h.number_compressed_chunks::INTEGER,
        CASE 
            WHEN h.total_chunks > 0 
            THEN CONCAT(ROUND((h.number_compressed_chunks::NUMERIC / h.total_chunks::NUMERIC) * 100, 1), '%')
            ELSE '0%'
        END::TEXT as compression_ratio
    FROM timescaledb_information.hypertables h
    WHERE h.schema_name = 'public'
    ORDER BY h.table_name;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 완료 메시지
-- ========================================

DO $$
BEGIN
    RAISE NOTICE '=== TimescaleDB 하이퍼테이블 초기화 완료 ===';
    RAISE NOTICE '생성된 하이퍼테이블:';
    RAISE NOTICE '  - stock_prices (주가 데이터)';
    RAISE NOTICE '  - supply_demand (수급 데이터)';
    RAISE NOTICE '  - realtime_prices (실시간 가격)';
    RAISE NOTICE '  - market_indices (시장 지수)';
    RAISE NOTICE '  - trading_sessions (거래 세션)';
    RAISE NOTICE '';
    RAISE NOTICE '생성된 연속 집계:';
    RAISE NOTICE '  - daily_candles (일봉 집계)';
    RAISE NOTICE '  - hourly_realtime_summary (시간별 실시간 집계)';
    RAISE NOTICE '';
    RAISE NOTICE '압축 및 보관 정책이 설정되었습니다.';
    RAISE NOTICE '초기화가 성공적으로 완료되었습니다.';
END $$; 