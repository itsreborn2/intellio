"""트리거_완전_제거_및_배치_계산_전환

Revision ID: 08d15a142dac
Revises: b2266b27ee43
Create Date: 2025-06-05 15:58:11.895848

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '08d15a142dac'
down_revision = 'b2266b27ee43'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """트리거 및 트리거 함수 완전 제거"""
    
    # 1. 트리거 삭제
    op.execute(text("""
        DROP TRIGGER IF EXISTS stock_price_auto_calculation_trigger ON stock_prices;
    """))
    
    # 2. 트리거 함수 삭제
    op.execute(text("""
        DROP FUNCTION IF EXISTS calculate_stock_price_changes();
    """))
    
    print("✅ 주가 데이터 자동계산 트리거 및 함수 완전 제거 완료")
    print("📝 이제 변동률 계산은 배치 처리로만 수행됩니다")


def downgrade() -> None:
    """트리거 및 트리거 함수 복원"""
    
    # 트리거 함수 재생성
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
    CREATE TRIGGER stock_price_auto_calculation_trigger
        BEFORE INSERT ON stock_prices
        FOR EACH ROW
        EXECUTE FUNCTION calculate_stock_price_changes();
    """
    
    op.execute(text(trigger_function_sql))
    op.execute(text(trigger_sql)) 