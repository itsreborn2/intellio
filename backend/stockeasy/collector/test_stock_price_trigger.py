"""
StockPrice 테이블 자동계산 트리거 테스트
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.config import get_settings
from models.timescale_models import StockPrice, TimescaleBase


async def test_stock_price_auto_calculation():
    """주가 데이터 자동계산 트리거 테스트"""
    
    settings = get_settings()
    engine = create_engine(settings.TIMESCALE_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    
    # 테스트 데이터 준비
    test_symbol = "005930"  # 삼성전자
    base_time = datetime(2024, 1, 15, 15, 30, 0)  # 2024년 1월 15일 15:30
    
    test_data = [
        {
            "time": base_time - timedelta(days=2),
            "close": Decimal("70000"),
            "volume": 1000000
        },
        {
            "time": base_time - timedelta(days=1),
            "close": Decimal("72000"), 
            "volume": 1200000
        },
        {
            "time": base_time,
            "close": Decimal("75000"),
            "volume": 1500000
        }
    ]
    
    session = Session()
    
    try:
        print("=== StockPrice 자동계산 트리거 테스트 시작 ===")
        
        # 기존 테스트 데이터 삭제
        session.execute(
            text("DELETE FROM stock_prices WHERE symbol = :symbol"),
            {"symbol": test_symbol}
        )
        session.commit()
        
        # 테스트 데이터 삽입
        for i, data in enumerate(test_data):
            stock_price = StockPrice(
                time=data["time"],
                symbol=test_symbol,
                interval_type="1d",
                open=data["close"] - Decimal("500"),
                high=data["close"] + Decimal("1000"),
                low=data["close"] - Decimal("1000"),
                close=data["close"],
                volume=data["volume"],
                trading_value=data["close"] * data["volume"],
                # 다른 필드들은 트리거에서 자동 계산됨
            )
            
            session.add(stock_price)
            session.commit()
            
            print(f"데이터 {i+1} 삽입 완료: {data['time'].strftime('%Y-%m-%d')} - 종가: {data['close']:,}원")
        
        # 결과 조회 및 검증
        print("\n=== 자동계산 결과 확인 ===")
        
        results = session.query(StockPrice).filter(
            StockPrice.symbol == test_symbol
        ).order_by(StockPrice.time).all()
        
        for i, result in enumerate(results):
            print(f"\n[{i+1}] {result.time.strftime('%Y-%m-%d')}:")
            print(f"  종가: {result.close:,}원")
            print(f"  거래량: {result.volume:,}주")
            print(f"  전일종가: {result.previous_close_price or '없음'}")
            print(f"  전일대비: {result.change_amount or '없음'}")
            print(f"  등락율: {result.price_change_percent or '없음'}%")
            print(f"  거래량변화: {result.volume_change or '없음'}주")
            print(f"  거래량증감율: {result.volume_change_percent or '없음'}%")
            
            # 두 번째 데이터부터 계산 결과 검증
            if i > 0:
                prev_data = test_data[i-1]
                current_data = test_data[i]
                
                # 등락율 계산 검증
                expected_change_percent = round(
                    ((current_data["close"] - prev_data["close"]) / prev_data["close"] * 100), 4
                )
                
                # 거래량 증감율 계산 검증
                expected_volume_change_percent = round(
                    ((current_data["volume"] - prev_data["volume"]) / prev_data["volume"] * 100), 4
                )
                
                print(f"  >>> 검증 결과:")
                print(f"      전일종가 정확성: {result.previous_close_price == prev_data['close']}")
                print(f"      등락율 정확성: {result.price_change_percent == expected_change_percent}")
                print(f"      거래량증감율 정확성: {result.volume_change_percent == expected_volume_change_percent}")
        
        print("\n=== 테스트 완료 ===")
        
        # 테스트 데이터 정리
        session.execute(
            text("DELETE FROM stock_prices WHERE symbol = :symbol"),
            {"symbol": test_symbol}
        )
        session.commit()
        print("테스트 데이터 정리 완료")
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(test_stock_price_auto_calculation()) 