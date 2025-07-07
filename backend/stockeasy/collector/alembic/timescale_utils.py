"""
TimescaleDB 하이퍼테이블 관련 유틸리티 함수들
"""
from alembic import op
from sqlalchemy import text


def create_hypertable(table_name: str, time_column: str = 'time', chunk_time_interval: str = '1 day'):
    """TimescaleDB 하이퍼테이블 생성"""
    sql = f"""
    SELECT create_hypertable('{table_name}', '{time_column}', 
                           chunk_time_interval => INTERVAL '{chunk_time_interval}',
                           if_not_exists => TRUE);
    """
    op.execute(text(sql))


def drop_hypertable(table_name: str):
    """TimescaleDB 하이퍼테이블 삭제"""
    sql = f"DROP TABLE IF EXISTS {table_name} CASCADE;"
    op.execute(text(sql))


def create_compression_policy(table_name: str, compress_after: str = '7 days'):
    """압축 정책 생성"""
    sql = f"""
    SELECT add_compression_policy('{table_name}', INTERVAL '{compress_after}');
    """
    op.execute(text(sql))


def create_retention_policy(table_name: str, drop_after: str = '1 year'):
    """보존 정책 생성"""
    sql = f"""
    SELECT add_retention_policy('{table_name}', INTERVAL '{drop_after}');
    """
    op.execute(text(sql))


def enable_compression(table_name: str):
    """테이블 압축 활성화"""
    sql = f"""
    ALTER TABLE {table_name} SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'symbol'
    );
    """
    op.execute(text(sql))


def create_stock_price_auto_calculation_trigger():
    """주가 데이터 자동 계산 트리거 생성"""
    
    # 트리거 함수 생성
    trigger_function_sql = """
    CREATE OR REPLACE FUNCTION calculate_stock_price_changes()
    RETURNS TRIGGER AS $$
    DECLARE
        prev_close NUMERIC(12,2);
        prev_volume BIGINT;
    BEGIN
        -- 이전 봉 데이터 조회 (같은 종목, 같은 간격, 이전 시간)
        SELECT close, volume 
        INTO prev_close, prev_volume
        FROM stock_prices 
        WHERE symbol = NEW.symbol 
          AND interval_type = NEW.interval_type 
          AND time < NEW.time
        ORDER BY time DESC 
        LIMIT 1;
        
        -- 이전 데이터가 있는 경우 계산
        IF prev_close IS NOT NULL THEN
            -- 전일종가 설정
            NEW.previous_close_price = prev_close;
            
            -- 전일대비 변동금액 계산
            NEW.change_amount = NEW.close - prev_close;
            
            -- 전일대비 등락율 계산 (%)
            IF prev_close > 0 THEN
                NEW.price_change_percent = ROUND(((NEW.close - prev_close) / prev_close * 100)::NUMERIC, 4);
            END IF;
        END IF;
        
        -- 이전 거래량이 있는 경우 계산
        IF prev_volume IS NOT NULL THEN
            -- 전일대비 거래량 변화
            NEW.volume_change = NEW.volume - prev_volume;
            
            -- 전일대비 거래량 증감율 계산 (%)
            IF prev_volume > 0 THEN
                NEW.volume_change_percent = ROUND(((NEW.volume - prev_volume)::NUMERIC / prev_volume * 100), 4);
            END IF;
        END IF;
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    
    # 트리거 생성
    trigger_sql = """
    DROP TRIGGER IF EXISTS stock_price_auto_calculation_trigger ON stock_prices;
    
    CREATE TRIGGER stock_price_auto_calculation_trigger
        BEFORE INSERT ON stock_prices
        FOR EACH ROW
        EXECUTE FUNCTION calculate_stock_price_changes();
    """
    
    op.execute(text(trigger_function_sql))
    op.execute(text(trigger_sql))


def drop_stock_price_auto_calculation_trigger():
    """주가 데이터 자동 계산 트리거 삭제"""
    
    drop_trigger_sql = """
    DROP TRIGGER IF EXISTS stock_price_auto_calculation_trigger ON stock_prices;
    DROP FUNCTION IF EXISTS calculate_stock_price_changes();
    """
    
    op.execute(text(drop_trigger_sql))


def create_stock_price_indexes():
    """주가 데이터 추가 인덱스 생성"""
    
    # 성능 최적화를 위한 추가 인덱스들
    indexes_sql = """
    -- 종목별 시간 역순 인덱스 (최근 데이터 조회용)
    CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_time_desc 
    ON stock_prices (symbol, time DESC, interval_type);
    
    -- 거래량 기준 정렬 인덱스
    CREATE INDEX IF NOT EXISTS idx_stock_prices_volume_desc 
    ON stock_prices (volume DESC, time DESC) WHERE interval_type = '1d';
    
    -- 등락율 기준 정렬 인덱스
    CREATE INDEX IF NOT EXISTS idx_stock_prices_change_percent 
    ON stock_prices (price_change_percent DESC, time DESC) WHERE interval_type = '1d';
    
    -- 심볼과 간격 타입 조합 인덱스
    CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_interval_time 
    ON stock_prices (symbol, interval_type, time DESC);
    """
    
    op.execute(text(indexes_sql))


def drop_stock_price_indexes():
    """주가 데이터 추가 인덱스 삭제"""
    
    drop_indexes_sql = """
    DROP INDEX IF EXISTS idx_stock_prices_symbol_time_desc;
    DROP INDEX IF EXISTS idx_stock_prices_volume_desc;
    DROP INDEX IF EXISTS idx_stock_prices_change_percent;
    DROP INDEX IF EXISTS idx_stock_prices_symbol_interval_time;
    """
    
    op.execute(text(drop_indexes_sql)) 