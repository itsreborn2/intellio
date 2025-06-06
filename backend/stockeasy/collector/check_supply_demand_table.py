#!/usr/bin/env python3
"""
Supply Demand 테이블 구조 확인 스크립트
"""
import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 환경변수 설정
os.environ.setdefault("TIMESCALE_PASSWORD", "StockCollector2024")
os.environ.setdefault("TIMESCALE_HOST", "localhost")
os.environ.setdefault("TIMESCALE_PORT", "6433")
os.environ.setdefault("TIMESCALE_USER", "collector_user")
os.environ.setdefault("TIMESCALE_DB", "stockeasy_collector")

from sqlalchemy import text
from backend.stockeasy.collector.core.timescale_database import get_timescale_session_context


async def check_supply_demand_table():
    """Supply Demand 테이블 구조 확인"""
    try:
        async with get_timescale_session_context() as session:
            # 테이블 컬럼 정보 조회
            query = text("""
                SELECT 
                    column_name, 
                    data_type, 
                    ordinal_position,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = 'supply_demand' 
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            
            result = await session.execute(query)
            columns = result.fetchall()
            
            print("=== Supply Demand 테이블 구조 ===")
            print(f"{'순서':<4} {'컬럼명':<25} {'타입':<20} {'NULL허용':<8} {'기본값':<15}")
            print("-" * 80)
            
            for col in columns:
                print(f"{col.ordinal_position:<4} {col.column_name:<25} {col.data_type:<20} {col.is_nullable:<8} {col.column_default or 'None':<15}")
            
            print(f"\n총 {len(columns)}개 컬럼")
            
            # 샘플 데이터 조회
            sample_query = text("SELECT * FROM supply_demand LIMIT 1")
            sample_result = await session.execute(sample_query)
            sample_row = sample_result.fetchone()
            
            if sample_row:
                print("\n=== 샘플 데이터 ===")
                for i, value in enumerate(sample_row):
                    col_name = columns[i].column_name if i < len(columns) else f"col_{i}"
                    print(f"{i}: {col_name} = {value} ({type(value).__name__})")
            else:
                print("\n샘플 데이터가 없습니다.")
                
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_supply_demand_table()) 