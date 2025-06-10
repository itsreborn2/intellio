"""수급_데이터_price_change_percent_precision_증가

Revision ID: fix_price_change_percent_precision
Revises: b2266b27ee43
Create Date: 2025-06-05 18:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_price_change_percent_precision'
down_revision = 'b2266b27ee43'  
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    1. 불필요한 테이블 삭제: realtime_prices, trading_session
    2. 필요한 테이블의 price_change_percent 필드 precision을 8,4에서 10,4로 변경
    사용자가 수동으로 데이터를 삭제한 후 구조만 변경
    기존: Numeric(8,4) - 최대 9999.9999
    변경: Numeric(10,4) - 최대 999999.9999
    """
    
    print("🗑️  불필요한 테이블 삭제 시작")
    _drop_unnecessary_tables()
    
    print("📊 필요한 테이블 구조 변경 시작 - precision 8,4 → 10,4")
    _modify_supply_demand_precision()
    _modify_market_indices_precision()
    _modify_stock_prices_precision()
    
    print("✅ 모든 작업 완료")


def _drop_unnecessary_tables():
    """불필요한 테이블들 삭제"""
    
    # realtime_prices 테이블 삭제
    print("🗑️  realtime_prices 테이블 삭제")
    op.execute("DROP TABLE IF EXISTS realtime_prices CASCADE;")
    
    # trading_session 테이블 삭제
    print("🗑️  trading_session 테이블 삭제")
    op.execute("DROP TABLE IF EXISTS trading_session CASCADE;")


def _modify_supply_demand_precision():
    """supply_demand 테이블 precision 변경"""
    print("🔧 supply_demand 테이블 price_change_percent precision 변경")
    
    # 1. 컬럼 타입 변경
    op.execute("""
        ALTER TABLE supply_demand 
        ALTER COLUMN price_change_percent TYPE NUMERIC(10,4);
    """)
    
    # 2. 컬럼 코멘트 업데이트  
    op.execute("""
        COMMENT ON COLUMN supply_demand.price_change_percent IS '등락율(%) - precision 10,4';
    """)


def _modify_market_indices_precision():
    """market_indices 테이블 precision 변경"""
    print("🔧 market_indices 테이블 price_change_percent precision 변경")
    
    # 1. 컬럼 타입 변경
    op.execute("""
        ALTER TABLE market_indices 
        ALTER COLUMN price_change_percent TYPE NUMERIC(10,4);
    """)
    
    # 2. 컬럼 코멘트 업데이트
    op.execute("""
        COMMENT ON COLUMN market_indices.price_change_percent IS '전일대비 변동률(%) - precision 10,4';
    """)


def _modify_stock_prices_precision():
    """stock_prices 테이블 precision 변경"""
    print("🔧 stock_prices 테이블 precision 변경")
    
    # 1. price_change_percent 컬럼 타입 변경
    op.execute("""
        ALTER TABLE stock_prices 
        ALTER COLUMN price_change_percent TYPE NUMERIC(10,4);
    """)
    
    # 2. volume_change_percent 컬럼 타입 변경
    op.execute("""
        ALTER TABLE stock_prices 
        ALTER COLUMN volume_change_percent TYPE NUMERIC(10,4);
    """)
    
    # 3. 컬럼 코멘트 업데이트
    op.execute("""
        COMMENT ON COLUMN stock_prices.price_change_percent IS '전일대비 등락율(%) - precision 10,4';
    """)
    
    op.execute("""
        COMMENT ON COLUMN stock_prices.volume_change_percent IS '전일대비 거래량 증감율(%) - precision 10,4';
    """)


def downgrade() -> None:
    """
    롤백: precision을 다시 8,4로 되돌림
    삭제된 테이블들은 복원하지 않음 (불필요한 테이블이므로)
    """
    
    print("⏪ 롤백: precision을 8,4로 되돌립니다")
    
    # stock_prices 롤백
    op.execute("""
        ALTER TABLE stock_prices 
        ALTER COLUMN price_change_percent TYPE NUMERIC(8,4);
    """)
    
    op.execute("""
        ALTER TABLE stock_prices 
        ALTER COLUMN volume_change_percent TYPE NUMERIC(8,4);
    """)
    
    # market_indices 롤백
    op.execute("""
        ALTER TABLE market_indices 
        ALTER COLUMN price_change_percent TYPE NUMERIC(8,4);
    """)
    
    # supply_demand 롤백
    op.execute("""
        ALTER TABLE supply_demand 
        ALTER COLUMN price_change_percent TYPE NUMERIC(8,4);
    """)
    
    print("✅ 롤백 완료")
    print("ℹ️  참고: 삭제된 테이블들(realtime_prices, trading_session)은 복원되지 않습니다.") 