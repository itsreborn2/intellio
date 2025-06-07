-- TimescaleDB 하이퍼테이블 완전 재생성
-- 모든 기존 테이블 삭제 후 현재 모델에 맞게 재생성

-- ========================================
-- 기존 테이블 및 관련 객체 완전 삭제
-- ========================================

-- 연속 집계 뷰 삭제
DROP MATERIALIZED VIEW IF EXISTS daily_candles CASCADE;
DROP MATERIALIZED VIEW IF EXISTS hourly_realtime_summary CASCADE;

-- 기존 테이블 삭제 (CASCADE로 모든 의존성 포함)
DROP TABLE IF EXISTS realtime_prices CASCADE;
DROP TABLE IF EXISTS trading_sessions CASCADE;
DROP TABLE IF EXISTS stock_prices CASCADE;
DROP TABLE IF EXISTS supply_demand CASCADE;
DROP TABLE IF EXISTS market_indices CASCADE;

-- 기존 함수 삭제
DROP FUNCTION IF EXISTS get_compression_stats();
DROP FUNCTION IF EXISTS get_hypertable_info();

-- ========================================
-- 새 테이블 생성 (현재 모델 기준)
-- ========================================

-- 주가 데이터 테이블 (StockPrice 모델 기준)
CREATE TABLE stock_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    interval_type VARCHAR(10) NOT NULL DEFAULT '1d',
    
    -- OHLCV 기본 데이터
    open NUMERIC(12,2),
    high NUMERIC(12,2),
    low NUMERIC(12,2),
    close NUMERIC(12,2),
    volume BIGINT,
    trading_value BIGINT,
    
    -- 변동 정보 (precision 10,4로 변경)
    change_amount NUMERIC(12,2),
    price_change_percent NUMERIC(10,4),
    volume_change BIGINT,
    volume_change_percent NUMERIC(10,4),
    
    -- 기준가 정보
    previous_close_price NUMERIC(12,2),
    
    -- 수정주가 관련 정보
    adjusted_price_type VARCHAR(20),
    adjustment_ratio NUMERIC(10,6),
    adjusted_price_event VARCHAR(100),
    
    -- 업종 분류
    major_industry_type VARCHAR(20),
    minor_industry_type VARCHAR(20),
    stock_info TEXT,
    
    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (time, symbol, interval_type)
);

-- 수급 데이터 테이블 (SupplyDemand 모델 기준)
CREATE TABLE supply_demand (
    date TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    
    -- 현재가 정보
    current_price NUMERIC(12,2),
    price_change_sign VARCHAR(5),
    price_change NUMERIC(12,2),
    price_change_percent NUMERIC(10,4),  -- precision 10,4로 변경
    
    -- 거래 정보
    accumulated_volume BIGINT,
    accumulated_value BIGINT,
    
    -- 투자자별 수급 데이터
    individual_investor BIGINT,
    foreign_investor BIGINT,
    institution_total BIGINT,
    
    -- 기관 세부 분류
    financial_investment BIGINT,
    insurance BIGINT,
    investment_trust BIGINT,
    other_financial BIGINT,
    bank BIGINT,
    pension_fund BIGINT,
    private_fund BIGINT,
    
    -- 기타 분류
    government BIGINT,
    other_corporation BIGINT,
    domestic_foreign BIGINT,
    
    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (date, symbol)
);

-- 시장 지수 테이블 (MarketIndex 모델 기준)
CREATE TABLE market_indices (
    time TIMESTAMPTZ NOT NULL,
    index_code VARCHAR(20) NOT NULL,
    
    -- 지수 정보
    index_value NUMERIC(12,2) NOT NULL,
    change_amount NUMERIC(12,2),
    price_change_percent NUMERIC(10,4),  -- precision 10,4로 변경
    
    -- 거래 정보
    volume BIGINT,
    trading_value BIGINT,
    
    -- 시장 정보
    rise_count INTEGER,
    fall_count INTEGER,
    unchanged_count INTEGER,
    
    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (time, index_code)
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

-- 시장 지수 하이퍼테이블 (1일 청크)
SELECT create_hypertable(
    'market_indices', 
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ========================================
-- 인덱스 생성
-- ========================================

-- 주가 데이터 인덱스
CREATE INDEX idx_stock_prices_symbol_time 
    ON stock_prices (symbol, time DESC, interval_type);
CREATE INDEX idx_stock_prices_symbol_interval 
    ON stock_prices (symbol, interval_type);
CREATE INDEX idx_stock_prices_time_desc 
    ON stock_prices (time DESC);

-- 수급 데이터 인덱스
CREATE INDEX idx_supply_demand_symbol_date 
    ON supply_demand (symbol, date DESC);
CREATE INDEX idx_supply_demand_date_desc 
    ON supply_demand (date DESC);

-- 시장 지수 인덱스
CREATE INDEX idx_market_indices_index_time 
    ON market_indices (index_code, time DESC);
CREATE INDEX idx_market_indices_time_desc 
    ON market_indices (time DESC);

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

-- 시장 지수 압축 설정 (30일 후)
ALTER TABLE market_indices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'index_code',
    timescaledb.compress_orderby = 'time DESC'
);

-- ========================================
-- 압축 정책 추가
-- ========================================

-- 주가 데이터 압축 정책 (30일 후 압축)
SELECT add_compression_policy('stock_prices', INTERVAL '30 days');

-- 수급 데이터 압축 정책 (90일 후 압축)
SELECT add_compression_policy('supply_demand', INTERVAL '90 days');

-- 시장 지수 압축 정책 (30일 후 압축)
SELECT add_compression_policy('market_indices', INTERVAL '30 days');

-- ========================================
-- 데이터 보관 정책
-- ========================================

-- 1분봉 데이터는 1년 보관
SELECT add_retention_policy('stock_prices', INTERVAL '1 year');

-- ========================================
-- 연속 집계 (Continuous Aggregates) 생성
-- ========================================

-- 일봉 연속 집계 뷰 (1분봉에서 일봉 생성)
CREATE MATERIALIZED VIEW daily_candles
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
    last(price_change_percent, time) as price_change_percent
FROM stock_prices
WHERE interval_type = '1m'  -- 1분봉에서만 일봉 생성
GROUP BY day, symbol, interval_type;

-- ========================================
-- 연속 집계 자동 갱신 정책
-- ========================================

-- 일봉 연속 집계 자동 갱신 (1시간마다)
SELECT add_continuous_aggregate_policy('daily_candles',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- ========================================
-- 유틸리티 함수 생성
-- ========================================

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
    WHERE h.schema_name = 'public'
    GROUP BY h.schema_name, h.table_name, h.total_chunks, h.number_compressed_chunks;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 코멘트 추가
-- ========================================

-- 테이블 코멘트
COMMENT ON TABLE stock_prices IS '주가 데이터 - TimescaleDB 하이퍼테이블';
COMMENT ON TABLE supply_demand IS '수급 데이터 - TimescaleDB 하이퍼테이블';
COMMENT ON TABLE market_indices IS '시장 지수 데이터 - TimescaleDB 하이퍼테이블';

-- 주요 컬럼 코멘트
COMMENT ON COLUMN stock_prices.time IS '시간 (UTC)';
COMMENT ON COLUMN stock_prices.symbol IS '종목코드';
COMMENT ON COLUMN stock_prices.price_change_percent IS '전일대비 등락율(%) - precision 10,4';
COMMENT ON COLUMN stock_prices.volume_change_percent IS '전일대비 거래량 증감율(%) - precision 10,4';

COMMENT ON COLUMN supply_demand.date IS '날짜';
COMMENT ON COLUMN supply_demand.symbol IS '종목코드';
COMMENT ON COLUMN supply_demand.price_change_percent IS '등락율(%) - precision 10,4';

COMMENT ON COLUMN market_indices.time IS '시간 (UTC)';
COMMENT ON COLUMN market_indices.index_code IS '지수 코드 (KOSPI, KOSDAQ)';
COMMENT ON COLUMN market_indices.price_change_percent IS '전일대비 변동률(%) - precision 10,4';

-- ========================================
-- 완료 메시지
-- ========================================

DO $$
BEGIN
    RAISE NOTICE '=== TimescaleDB 하이퍼테이블 재생성 완료 ===';
    RAISE NOTICE '삭제된 테이블:';
    RAISE NOTICE '  - realtime_prices (불필요)';
    RAISE NOTICE '  - trading_sessions (불필요)';
    RAISE NOTICE '';
    RAISE NOTICE '생성된 하이퍼테이블:';
    RAISE NOTICE '  - stock_prices (주가 데이터) - precision 10,4';
    RAISE NOTICE '  - supply_demand (수급 데이터) - precision 10,4';
    RAISE NOTICE '  - market_indices (시장 지수) - precision 10,4';
    RAISE NOTICE '';
    RAISE NOTICE '생성된 연속 집계:';
    RAISE NOTICE '  - daily_candles (일봉 집계)';
    RAISE NOTICE '';
    RAISE NOTICE '압축 및 보관 정책이 설정되었습니다.';
    RAISE NOTICE '모든 precision이 10,4로 업데이트되었습니다.';
    RAISE NOTICE '재생성이 성공적으로 완료되었습니다.';
END $$; 