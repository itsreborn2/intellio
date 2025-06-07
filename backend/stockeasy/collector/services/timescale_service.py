"""
TimescaleDB 전용 서비스 클래스
시계열 데이터의 효율적인 저장 및 조회를 위한 서비스
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal

from sqlalchemy import text, select, insert, update, delete, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from loguru import logger

from ..core.timescale_database import (
    get_timescale_session_context, 
    TimescaleConnectionMonitor,
    create_timescale_session
)
from ..models.timescale_models import (
    StockPrice, 
    SupplyDemand, 
    MarketIndex, 
    TimescaleBase
)
from ..schemas.timescale_schemas import (
    StockPriceCreate,
    StockPriceResponse,
    SupplyDemandCreate,
    SupplyDemandResponse,
    RealtimePriceCreate,
    RealtimePriceResponse,
    MarketIndexCreate,
    MarketIndexResponse,
    IntervalType,
    CandleData,
    CandleResponse,
    BulkStockPriceCreate,
    BulkSupplyDemandCreate,
    TimescaleHealthCheck,
    TimescaleStats
)


class TimescaleService:
    """TimescaleDB 전용 서비스 클래스"""
    
    def __init__(self):
        """서비스 초기화"""
        self.logger = logger.bind(service="TimescaleService")
        self.connection_monitor = TimescaleConnectionMonitor()
        self._initialized = False
    
    async def initialize(self) -> None:
        """서비스 초기화 및 테이블 생성"""
        if self._initialized:
            return
            
        try:
            async with get_timescale_session_context() as session:
                # 테이블 존재 여부 확인
                result = await session.execute(
                    text("SELECT tablename FROM pg_tables WHERE tablename = 'stock_prices'")
                )
                if not result.fetchone():
                    # 테이블이 없으면 생성
                    await self._create_tables(session)
                    await self._create_hypertables(session)
                    await self._setup_indexes(session)
                
                self._initialized = True
                self.logger.info("TimescaleDB 서비스 초기화 완료")
                
        except Exception as e:
            self.logger.error(f"TimescaleDB 서비스 초기화 실패: {e}")
            raise
    
    # ========================================
    # 초기화 관련 내부 메서드
    # ========================================
    
    async def _create_tables(self, session: AsyncSession) -> None:
        """테이블 생성"""
        # SQLAlchemy 메타데이터를 사용하여 테이블 생성
        from sqlalchemy import MetaData
        from ..core.timescale_database import timescale_async_engine
        
        async with timescale_async_engine.begin() as conn:
            await conn.run_sync(TimescaleBase.metadata.create_all)
        
        self.logger.info("TimescaleDB 테이블 생성 완료")
    
    async def _create_hypertables(self, session: AsyncSession) -> None:
        """하이퍼테이블 생성"""
        hypertable_queries = [
            "SELECT create_hypertable('stock_prices', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)",
            "SELECT create_hypertable('supply_demand', 'date', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)",
            "SELECT create_hypertable('realtime_prices', 'time', chunk_time_interval => INTERVAL '1 hour', if_not_exists => TRUE)",
            "SELECT create_hypertable('market_indices', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)",
            "SELECT create_hypertable('trading_sessions', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)"
        ]
        
        for query in hypertable_queries:
            try:
                await session.execute(text(query))
                await session.commit()
            except Exception as e:
                self.logger.warning(f"하이퍼테이블 생성 중 오류 (무시 가능): {e}")
        
        self.logger.info("TimescaleDB 하이퍼테이블 생성 완료")
    
    async def _setup_indexes(self, session: AsyncSession) -> None:
        """인덱스 생성"""
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_time ON stock_prices (symbol, time DESC, interval_type)",
            "CREATE INDEX IF NOT EXISTS idx_supply_demand_symbol_date ON supply_demand (symbol, date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_realtime_prices_symbol_time ON realtime_prices (symbol, time DESC)"
        ]
        
        for query in index_queries:
            try:
                await session.execute(text(query))
                await session.commit()
            except Exception as e:
                self.logger.warning(f"인덱스 생성 중 오류 (무시 가능): {e}")
        
        self.logger.info("TimescaleDB 인덱스 생성 완료")
    
    # ========================================
    # 주가 데이터 관련 메서드
    # ========================================
    
    async def create_stock_price(self, stock_price: StockPriceCreate) -> StockPriceResponse:
        """단일 주가 데이터 생성"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                db_obj = StockPrice(**stock_price.dict())
                session.add(db_obj)
                await session.flush()
                await session.refresh(db_obj)
                
                return StockPriceResponse.from_orm(db_obj)
                
        except IntegrityError:
            # 중복 데이터 처리 (upsert)
            return await self.upsert_stock_price(stock_price)
        except Exception as e:
            self.logger.error(f"주가 데이터 생성 실패: {e}")
            raise
    


    async def bulk_create_stock_prices(self, prices: BulkStockPriceCreate) -> Dict[str, Any]:
        """주가 데이터 대량 생성 (성능 최적화 버전 - 트리거 없음)"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                # 배치 삽입을 위한 데이터 준비
                price_dicts = [price.dict() for price in prices.prices]
                
                # 성능 최적화: INSERT ONLY 방식 (중복 체크 없이 빠른 삽입)
                # 대용량 데이터의 경우 중복보다는 속도를 우선
                insert_query = text("""
                    INSERT INTO stock_prices (time, symbol, interval_type, open, high, low, close, volume, trading_value, 
                                            adjusted_price_type, adjustment_ratio, adjusted_price_event,
                                            major_industry_type, minor_industry_type, stock_info, created_at)
                    VALUES (:time, :symbol, :interval_type, :open, :high, :low, :close, :volume, :trading_value,
                           :adjusted_price_type, :adjustment_ratio, :adjusted_price_event,
                           :major_industry_type, :minor_industry_type, :stock_info, :created_at)
                    ON CONFLICT (time, symbol, interval_type) DO NOTHING
                """)
                
                # created_at 필드 추가 및 None 값 처리
                current_time = datetime.utcnow()
                for price_dict in price_dicts:
                    price_dict['created_at'] = current_time
                    # 새로운 필드들에 대한 기본값 설정
                    for field in ['adjusted_price_type', 'adjustment_ratio', 'adjusted_price_event',
                                'major_industry_type', 'minor_industry_type', 'stock_info']:
                        if field not in price_dict:
                            price_dict[field] = None
                
                # 대량 삽입 실행
                await session.execute(insert_query, price_dicts)
                
                self.logger.info(f"주가 데이터 {len(price_dicts)}건 대량 삽입 완료 (트리거 없음)")
                
                return {
                    "success": True,
                    "inserted_count": len(price_dicts),
                    "message": f"{len(price_dicts)}건의 주가 데이터가 성공적으로 저장되었습니다"
                }
                
        except Exception as e:
            self.logger.error(f"주가 데이터 대량 생성 실패: {e}")
            raise
    
    async def bulk_create_stock_prices_with_upsert(self, prices: BulkStockPriceCreate) -> Dict[str, Any]:
        """주가 데이터 대량 생성 (upsert 버전 - 정확성 우선)"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                # 배치 삽입을 위한 데이터 준비
                price_dicts = [price.dict() for price in prices.prices]
                
                # ON CONFLICT를 사용한 upsert - 새로운 필드 구조 반영
                upsert_query = text("""
                    INSERT INTO stock_prices (time, symbol, interval_type, open, high, low, close, volume, trading_value, 
                                            adjusted_price_type, adjustment_ratio, adjusted_price_event,
                                            major_industry_type, minor_industry_type, stock_info, created_at)
                    VALUES (:time, :symbol, :interval_type, :open, :high, :low, :close, :volume, :trading_value,
                           :adjusted_price_type, :adjustment_ratio, :adjusted_price_event,
                           :major_industry_type, :minor_industry_type, :stock_info, :created_at)
                    ON CONFLICT (time, symbol, interval_type) 
                    DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        trading_value = EXCLUDED.trading_value,
                        adjusted_price_type = EXCLUDED.adjusted_price_type,
                        adjustment_ratio = EXCLUDED.adjustment_ratio,
                        adjusted_price_event = EXCLUDED.adjusted_price_event,
                        major_industry_type = EXCLUDED.major_industry_type,
                        minor_industry_type = EXCLUDED.minor_industry_type,
                        stock_info = EXCLUDED.stock_info,
                        created_at = EXCLUDED.created_at
                """)
                
                # created_at 필드 추가 및 None 값 처리
                current_time = datetime.utcnow()
                for price_dict in price_dicts:
                    price_dict['created_at'] = current_time
                    # 새로운 필드들에 대한 기본값 설정
                    for field in ['adjusted_price_type', 'adjustment_ratio', 'adjusted_price_event',
                                'major_industry_type', 'minor_industry_type', 'stock_info']:
                        if field not in price_dict:
                            price_dict[field] = None
                
                await session.execute(upsert_query, price_dicts)
                
                self.logger.info(f"주가 데이터 {len(price_dicts)}건 upsert 완료")
                
                return {
                    "success": True,
                    "inserted_count": len(price_dicts),
                    "message": f"{len(price_dicts)}건의 주가 데이터가 성공적으로 저장되었습니다"
                }
                
        except Exception as e:
            self.logger.error(f"주가 데이터 대량 생성 실패: {e}")
            raise
    
    async def upsert_stock_price(self, stock_price: StockPriceCreate) -> StockPriceResponse:
        """주가 데이터 upsert (존재하면 업데이트, 없으면 생성)"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                upsert_query = text("""
                    INSERT INTO stock_prices (time, symbol, interval_type, open, high, low, close, volume, trading_value, 
                                            adjusted_price_type, adjustment_ratio, adjusted_price_event,
                                            major_industry_type, minor_industry_type, stock_info, created_at)
                    VALUES (:time, :symbol, :interval_type, :open, :high, :low, :close, :volume, :trading_value,
                           :adjusted_price_type, :adjustment_ratio, :adjusted_price_event,
                           :major_industry_type, :minor_industry_type, :stock_info, :created_at)
                    ON CONFLICT (time, symbol, interval_type) 
                    DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        trading_value = EXCLUDED.trading_value,
                        adjusted_price_type = EXCLUDED.adjusted_price_type,
                        adjustment_ratio = EXCLUDED.adjustment_ratio,
                        adjusted_price_event = EXCLUDED.adjusted_price_event,
                        major_industry_type = EXCLUDED.major_industry_type,
                        minor_industry_type = EXCLUDED.minor_industry_type,
                        stock_info = EXCLUDED.stock_info,
                        created_at = EXCLUDED.created_at
                    RETURNING *
                """)
                
                price_dict = stock_price.dict()
                price_dict['created_at'] = datetime.utcnow()
                
                # 새로운 필드들에 대한 기본값 설정
                for field in ['adjusted_price_type', 'adjustment_ratio', 'adjusted_price_event',
                            'major_industry_type', 'minor_industry_type', 'stock_info']:
                    if field not in price_dict:
                        price_dict[field] = None
                
                result = await session.execute(upsert_query, price_dict)
                row = result.fetchone()
                
                if row:
                    return StockPriceResponse(
                        time=row.time,
                        symbol=row.symbol,
                        interval_type=row.interval_type,
                        open=row.open,
                        high=row.high,
                        low=row.low,
                        close=row.close,
                        volume=row.volume,
                        trading_value=row.trading_value,
                        change_amount=row.change_amount,
                        price_change_percent=row.price_change_percent,
                        volume_change=row.volume_change,
                        volume_change_percent=row.volume_change_percent,
                        previous_close_price=row.previous_close_price,
                        adjusted_price_type=row.adjusted_price_type,
                        adjustment_ratio=row.adjustment_ratio,
                        adjusted_price_event=row.adjusted_price_event,
                        major_industry_type=row.major_industry_type,
                        minor_industry_type=row.minor_industry_type,
                        stock_info=row.stock_info,
                        created_at=row.created_at
                    )
                else:
                    raise ValueError("Upsert 실행 후 결과가 없습니다")
                    
        except Exception as e:
            self.logger.error(f"주가 데이터 upsert 실패: {e}")
            raise
    
    async def get_stock_prices(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        interval_type: IntervalType = IntervalType.ONE_MINUTE,
        limit: int = 1000
    ) -> List[StockPriceResponse]:
        """주가 데이터 조회"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                query = select(StockPrice).where(
                    and_(
                        StockPrice.symbol == symbol,
                        StockPrice.interval_type == interval_type.value,
                        StockPrice.time >= start_date,
                        StockPrice.time <= end_date
                    )
                ).order_by(desc(StockPrice.time)).limit(limit)
                
                result = await session.execute(query)
                prices = result.scalars().all()
                
                return [StockPriceResponse.from_orm(price) for price in prices]
                
        except Exception as e:
            self.logger.error(f"주가 데이터 조회 실패: {e}")
            raise
    
    async def get_candle_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval_type: IntervalType = IntervalType.ONE_MINUTE
    ) -> CandleResponse:
        """캔들 차트 데이터 조회"""
        await self.initialize()
        
        try:
            prices = await self.get_stock_prices(symbol, start_date, end_date, interval_type)
            
            # 결과를 CandleData 형태로 변환
            candles = []
            for price in prices:
                candles.append(CandleData(
                    time=price.time,
                    open=price.open or Decimal(0),
                    high=price.high or Decimal(0),
                    low=price.low or Decimal(0),
                    close=price.close or Decimal(0),
                    volume=price.volume or 0,
                    price_change_percent=price.price_change_percent
                ))
            
            return CandleResponse(
                symbol=symbol,
                interval_type=interval_type,
                data=candles,
                total_count=len(candles),
                start_date=start_date,
                end_date=end_date
            )
            
        except Exception as e:
            self.logger.error(f"캔들 데이터 조회 실패: {e}")
            raise
    
    # ========================================
    # 실시간 가격 데이터 관련 메서드
    # ========================================
    
    async def create_realtime_price(self, realtime_price: RealtimePriceCreate) -> RealtimePriceResponse:
        """실시간 가격 데이터 생성"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                upsert_query = text("""
                    INSERT INTO realtime_prices (time, symbol, price, volume, bid_price, ask_price, bid_volume, ask_volume, change_amount, price_change_percent, trading_value, accumulated_volume, accumulated_value, market_status, is_suspended)
                    VALUES (:time, :symbol, :price, :volume, :bid_price, :ask_price, :bid_volume, :ask_volume, :change_amount, :price_change_percent, :trading_value, :accumulated_volume, :accumulated_value, :market_status, :is_suspended)
                    ON CONFLICT (time, symbol) 
                    DO UPDATE SET
                        price = EXCLUDED.price,
                        volume = EXCLUDED.volume,
                        bid_price = EXCLUDED.bid_price,
                        ask_price = EXCLUDED.ask_price,
                        bid_volume = EXCLUDED.bid_volume,
                        ask_volume = EXCLUDED.ask_volume,
                        change_amount = EXCLUDED.change_amount,
                        price_change_percent = EXCLUDED.price_change_percent,
                        trading_value = EXCLUDED.trading_value,
                        accumulated_volume = EXCLUDED.accumulated_volume,
                        accumulated_value = EXCLUDED.accumulated_value,
                        market_status = EXCLUDED.market_status,
                        is_suspended = EXCLUDED.is_suspended
                    RETURNING *
                """)
                
                result = await session.execute(upsert_query, realtime_price.dict())
                row = result.fetchone()
                
                if row:
                    # Row 객체를 딕셔너리로 변환 (SQLAlchemy 2.0 호환)
                    row_dict = {
                        'time': row[0],
                        'symbol': row[1],
                        'price': row[2], 
                        'volume': row[3],
                        'bid_price': row[4],
                        'ask_price': row[5],
                        'bid_volume': row[6],
                        'ask_volume': row[7],
                        'change_amount': row[8],
                        'price_change_percent': row[9],
                        'trading_value': row[10],
                        'accumulated_volume': row[11],
                        'accumulated_value': row[12],
                        'market_status': row[13],
                        'is_suspended': row[14]
                    }
                    return RealtimePriceResponse(**row_dict)
                else:
                    raise ValueError("실시간 가격 데이터 생성 실패")
                    
        except Exception as e:
            self.logger.error(f"실시간 가격 데이터 생성 실패: {e}")
            raise
    
    async def get_latest_realtime_price(self, symbol: str) -> Optional[RealtimePriceResponse]:
        """최신 실시간 가격 조회"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                query = select(RealtimePrice).where(
                    RealtimePrice.symbol == symbol
                ).order_by(desc(RealtimePrice.time)).limit(1)
                
                result = await session.execute(query)
                price = result.scalar_one_or_none()
                
                if price:
                    return RealtimePriceResponse.from_orm(price)
                return None
                
        except Exception as e:
            self.logger.error(f"최신 실시간 가격 조회 실패: {e}")
            raise
    
    # ========================================
    # 수급 데이터 관련 메서드
    # ========================================
    
    async def create_supply_demand(self, supply_demand: SupplyDemandCreate) -> SupplyDemandResponse:
        """수급 데이터 생성"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                # upsert 방식으로 처리 - 새로운 스키마에 맞게 업데이트
                upsert_query = text("""
                    INSERT INTO supply_demand (date, symbol, current_price, price_change_sign, price_change, price_change_percent,
                                             accumulated_volume, accumulated_value, individual_investor, foreign_investor, institution_total,
                                             financial_investment, insurance, investment_trust, other_financial, bank, pension_fund, private_fund,
                                             government, other_corporation, domestic_foreign, created_at)
                    VALUES (:date, :symbol, :current_price, :price_change_sign, :price_change, :price_change_percent,
                           :accumulated_volume, :accumulated_value, :individual_investor, :foreign_investor, :institution_total,
                           :financial_investment, :insurance, :investment_trust, :other_financial, :bank, :pension_fund, :private_fund,
                           :government, :other_corporation, :domestic_foreign, :created_at)
                    ON CONFLICT (date, symbol) 
                    DO UPDATE SET
                        current_price = EXCLUDED.current_price,
                        price_change_sign = EXCLUDED.price_change_sign,
                        price_change = EXCLUDED.price_change,
                        price_change_percent = EXCLUDED.price_change_percent,
                        accumulated_volume = EXCLUDED.accumulated_volume,
                        accumulated_value = EXCLUDED.accumulated_value,
                        individual_investor = EXCLUDED.individual_investor,
                        foreign_investor = EXCLUDED.foreign_investor,
                        institution_total = EXCLUDED.institution_total,
                        financial_investment = EXCLUDED.financial_investment,
                        insurance = EXCLUDED.insurance,
                        investment_trust = EXCLUDED.investment_trust,
                        other_financial = EXCLUDED.other_financial,
                        bank = EXCLUDED.bank,
                        pension_fund = EXCLUDED.pension_fund,
                        private_fund = EXCLUDED.private_fund,
                        government = EXCLUDED.government,
                        other_corporation = EXCLUDED.other_corporation,
                        domestic_foreign = EXCLUDED.domestic_foreign,
                        created_at = EXCLUDED.created_at
                    RETURNING *
                """)
                
                supply_dict = supply_demand.dict()
                supply_dict['created_at'] = datetime.utcnow()
                
                result = await session.execute(upsert_query, supply_dict)
                row = result.fetchone()
                
                if row:
                    # SQLAlchemy 2.0에서 Row 객체를 딕셔너리로 변환하는 올바른 방법
                    # 실제 테이블 컬럼 순서: date, symbol, created_at, current_price, price_change_sign, price_change, price_change_percent, ...
                    row_dict = {
                        'date': row[0],           # date
                        'symbol': row[1],         # symbol  
                        'created_at': row[2],     # created_at
                        'current_price': row[3],  # current_price
                        'price_change_sign': row[4],  # price_change_sign
                        'price_change': row[5],   # price_change
                        'price_change_percent': row[6],  # price_change_percent
                        'accumulated_volume': row[7],    # accumulated_volume
                        'accumulated_value': row[8],     # accumulated_value
                        'individual_investor': row[9],   # individual_investor
                        'foreign_investor': row[10],     # foreign_investor
                        'institution_total': row[11],    # institution_total
                        'financial_investment': row[12], # financial_investment
                        'insurance': row[13],            # insurance
                        'investment_trust': row[14],     # investment_trust
                        'other_financial': row[15],      # other_financial
                        'bank': row[16],                 # bank
                        'pension_fund': row[17],         # pension_fund
                        'private_fund': row[18],         # private_fund
                        'government': row[19],           # government
                        'other_corporation': row[20],    # other_corporation
                        'domestic_foreign': row[21]      # domestic_foreign
                    }
                    return SupplyDemandResponse(**row_dict)
                else:
                    raise ValueError("수급 데이터 생성 실패")
                    
        except Exception as e:
            self.logger.error(f"수급 데이터 생성 실패: {e}")
            raise
    
    async def get_supply_demand_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        limit: int = 1000
    ) -> List[SupplyDemandResponse]:
        """수급 데이터 조회 (data_collector에서 사용)"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                # 디버깅: 전체 데이터 건수 확인
                count_query = text("SELECT COUNT(*) FROM supply_demand WHERE symbol = :symbol")
                count_result = await session.execute(count_query, {"symbol": symbol})
                total_count = count_result.scalar()
                self.logger.info(f"수급 데이터 디버깅 - 종목 {symbol}의 전체 데이터 건수: {total_count}")
                
                # 디버깅: 날짜 범위 내 데이터 건수 확인 (날짜만 비교)
                date_count_query = text("""
                    SELECT COUNT(*) FROM supply_demand 
                    WHERE symbol = :symbol 
                    AND DATE(date) >= :start_date 
                    AND DATE(date) <= :end_date
                """)
                start_date_only = start_date.date() if hasattr(start_date, 'date') else start_date
                end_date_only = end_date.date() if hasattr(end_date, 'date') else end_date
                
                date_count_result = await session.execute(date_count_query, {
                    "symbol": symbol,
                    "start_date": start_date_only,
                    "end_date": end_date_only
                })
                date_count = date_count_result.scalar()
                self.logger.info(f"수급 데이터 디버깅 - 종목 {symbol}, 기간 {start_date_only}~{end_date_only} 데이터 건수: {date_count}")
                
                # 디버깅: 실제 날짜 범위 확인
                date_range_query = text("""
                    SELECT MIN(date) as min_date, MAX(date) as max_date 
                    FROM supply_demand WHERE symbol = :symbol
                """)
                date_range_result = await session.execute(date_range_query, {"symbol": symbol})
                date_range = date_range_result.fetchone()
                if date_range:
                    self.logger.info(f"수급 데이터 디버깅 - 종목 {symbol}의 실제 날짜 범위: {date_range.min_date} ~ {date_range.max_date}")
                
                # 실제 쿼리 실행 (날짜만 비교)
                query = select(SupplyDemand).where(
                    and_(
                        SupplyDemand.symbol == symbol,
                        text("DATE(supply_demand.date) >= :start_date"),
                        text("DATE(supply_demand.date) <= :end_date")
                    )
                ).order_by(asc(SupplyDemand.date)).limit(limit)
                
                # 파라미터 바인딩
                query = query.params(start_date=start_date_only, end_date=end_date_only)
                
                self.logger.info(f"수급 데이터 쿼리 실행 - symbol: {symbol}, start_date: {start_date}, end_date: {end_date}")
                
                result = await session.execute(query)
                supplies = result.scalars().all()
                
                self.logger.info(f"수급 데이터 조회 결과: {len(supplies)}건")
                
                return [SupplyDemandResponse.from_orm(supply) for supply in supplies]
                
        except Exception as e:
            self.logger.error(f"수급 데이터 조회 실패: {e}")
            raise

    
    
    async def bulk_create_supply_demand_data(self, supply_data_list: List[SupplyDemandCreate]) -> Dict[str, Any]:
        """수급 데이터 대량 생성"""
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                # 배치 삽입을 위한 데이터 준비
                supply_dicts = [supply.dict() for supply in supply_data_list]
                
                # ON CONFLICT를 사용한 upsert
                upsert_query = text("""
                    INSERT INTO supply_demand (date, symbol, current_price, price_change_sign, price_change, price_change_percent,
                                             accumulated_volume, accumulated_value, individual_investor, foreign_investor, institution_total,
                                             financial_investment, insurance, investment_trust, other_financial, bank, pension_fund, private_fund,
                                             government, other_corporation, domestic_foreign, created_at)
                    VALUES (:date, :symbol, :current_price, :price_change_sign, :price_change, :price_change_percent,
                           :accumulated_volume, :accumulated_value, :individual_investor, :foreign_investor, :institution_total,
                           :financial_investment, :insurance, :investment_trust, :other_financial, :bank, :pension_fund, :private_fund,
                           :government, :other_corporation, :domestic_foreign, :created_at)
                    ON CONFLICT (date, symbol) 
                    DO UPDATE SET
                        current_price = EXCLUDED.current_price,
                        price_change_sign = EXCLUDED.price_change_sign,
                        price_change = EXCLUDED.price_change,
                        price_change_percent = EXCLUDED.price_change_percent,
                        accumulated_volume = EXCLUDED.accumulated_volume,
                        accumulated_value = EXCLUDED.accumulated_value,
                        individual_investor = EXCLUDED.individual_investor,
                        foreign_investor = EXCLUDED.foreign_investor,
                        institution_total = EXCLUDED.institution_total,
                        financial_investment = EXCLUDED.financial_investment,
                        insurance = EXCLUDED.insurance,
                        investment_trust = EXCLUDED.investment_trust,
                        other_financial = EXCLUDED.other_financial,
                        bank = EXCLUDED.bank,
                        pension_fund = EXCLUDED.pension_fund,
                        private_fund = EXCLUDED.private_fund,
                        government = EXCLUDED.government,
                        other_corporation = EXCLUDED.other_corporation,
                        domestic_foreign = EXCLUDED.domestic_foreign,
                        created_at = EXCLUDED.created_at
                """)
                
                # created_at 필드 추가 및 None 값 처리, 데이터 유효성 검사
                valid_supply_dicts = []
                for supply_dict in supply_dicts:
                    supply_dict['created_at'] = datetime.utcnow()
                    
                    # 새로운 필드들에 대한 기본값 설정
                    for field in ['current_price', 'price_change_sign', 'price_change', 'price_change_percent',
                                'accumulated_volume', 'accumulated_value', 'individual_investor', 'foreign_investor', 
                                'institution_total', 'financial_investment', 'insurance', 'investment_trust', 
                                'other_financial', 'bank', 'pension_fund', 'private_fund',
                                'government', 'other_corporation', 'domestic_foreign']:
                        if field not in supply_dict:
                            supply_dict[field] = None
                    
                    # price_change_percent 값 유효성 검사 및 제한
                    if supply_dict.get('price_change_percent') is not None:
                        pcp = float(supply_dict['price_change_percent'])
                        if abs(pcp) > 999999.9999:  # Numeric(10,4) 최대값
                            self.logger.warning(f"수급 데이터 - 종목 {supply_dict.get('symbol')}, 날짜 {supply_dict.get('date')}: price_change_percent 값이 너무 큼 ({pcp}), 999999.9999로 제한")
                            supply_dict['price_change_percent'] = 999999.9999 if pcp > 0 else -999999.9999
                    
                    valid_supply_dicts.append(supply_dict)
                
                supply_dicts = valid_supply_dicts
                
                await session.execute(upsert_query, supply_dicts)
                
                self.logger.info(f"수급 데이터 {len(supply_dicts)}건 대량 삽입 완료")
                
                return {
                    "success": True,
                    "inserted_count": len(supply_dicts),
                    "message": f"{len(supply_dicts)}건의 수급 데이터가 성공적으로 저장되었습니다"
                }
                
        except Exception as e:
            self.logger.error(f"수급 데이터 대량 생성 실패: {e}")
            raise

    async def bulk_create_supply_demand_with_progress(
        self, 
        supply_data_list: List[SupplyDemandCreate], 
        batch_size: int = 500,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        수급 데이터 대량 생성 (진행상황 모니터링)
        
        Args:
            supply_data_list: 수급 데이터 리스트
            batch_size: 배치 크기 (기본값: 500)
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            Dict: 처리 결과
        """
        await self.initialize()
        
        total_count = len(supply_data_list)
        processed_count = 0
        success_count = 0
        error_count = 0
        
        try:
            # 배치 단위로 처리
            for i in range(0, total_count, batch_size):
                batch = supply_data_list[i:i + batch_size]
                
                try:
                    result = await self.bulk_create_supply_demand_data(batch)
                    if result.get("success"):
                        success_count += len(batch)
                    else:
                        error_count += len(batch)
                        
                except Exception as e:
                    self.logger.error(f"수급 데이터 배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                    error_count += len(batch)
                
                processed_count += len(batch)
                
                # 진행상황 알림
                if progress_callback:
                    progress = (processed_count / total_count) * 100
                    await progress_callback(processed_count, total_count, progress, success_count, error_count)
                
                # 메모리 정리를 위한 짧은 대기
                await asyncio.sleep(0.01)
            
            self.logger.info(f"수급 데이터 대량 처리 완료: 총 {total_count}건, 성공 {success_count}건, 실패 {error_count}건")
            
            return {
                "success": True,
                "total_count": total_count,
                "success_count": success_count,
                "error_count": error_count,
                "message": f"수급 데이터 대량 처리 완료: 성공 {success_count}건 / 실패 {error_count}건"
            }
            
        except Exception as e:
            self.logger.error(f"수급 데이터 대량 처리 실패: {e}")
            raise

    async def batch_calculate_stock_price_changes(
        self, 
        symbols: List[str] = None,
        days_back: int = 30,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        주가 데이터 변동률 배치 계산 (고성능)
        
        Args:
            symbols: 계산할 종목 리스트 (None이면 전체)
            days_back: 계산할 일수 (기본 30일)
            batch_size: 동시 처리할 종목 수
            
        Returns:
            Dict: 계산 결과
        """
        await self.initialize()
        
        try:
            start_time = datetime.utcnow()
            
            async with get_timescale_session_context() as session:
                # 대상 종목 조회
                if symbols is None:
                    symbol_query = text("""
                        SELECT DISTINCT symbol 
                        FROM stock_prices 
                        WHERE time >= NOW() - INTERVAL '%s days'
                        ORDER BY symbol
                        LIMIT 100
                    """ % days_back)
                    result = await session.execute(symbol_query)
                    symbols = [row[0] for row in result.fetchall()]
                
                self.logger.info(f"배치 계산 시작: {len(symbols)}개 종목, {days_back}일")
                
                total_updated = 0
                processed_symbols = 0
                
                # 종목별 배치 처리
                for i in range(0, len(symbols), batch_size):
                    batch_symbols = symbols[i:i + batch_size]
                    
                    # 배치 종목들의 데이터 일괄 조회
                    data_query = text("""
                        SELECT time, symbol, interval_type, close, volume, open, high, low
                        FROM stock_prices 
                        WHERE symbol = ANY(:symbols)
                          AND time >= NOW() - INTERVAL '%s days'
                          AND close IS NOT NULL
                        ORDER BY symbol, interval_type, time
                    """ % days_back)
                    
                    result = await session.execute(data_query, {"symbols": batch_symbols})
                    rows = result.fetchall()
                    
                    # 종목별 데이터 그룹화
                    symbol_data = {}
                    for row in rows:
                        key = (row.symbol, row.interval_type)
                        if key not in symbol_data:
                            symbol_data[key] = []
                        symbol_data[key].append({
                            'time': row.time,
                            'close': float(row.close),
                            'volume': int(row.volume) if row.volume else 0,
                            'open': float(row.open) if row.open else 0,
                            'high': float(row.high) if row.high else 0,
                            'low': float(row.low) if row.low else 0
                        })
                    
                    # 계산된 업데이트 데이터 준비
                    update_data = []
                    
                    # 각 종목별 계산
                    for (symbol, interval_type), data_list in symbol_data.items():
                        if len(data_list) < 2:
                            continue
                            
                        # 시간순 정렬 (이미 정렬되어 있지만 확실히)
                        data_list.sort(key=lambda x: x['time'])
                        
                        # 각 데이터포인트에 대해 이전 값과 비교하여 계산
                        for i in range(1, len(data_list)):
                            current = data_list[i]
                            previous = data_list[i-1]
                            
                            # 전일대비 계산
                            change_amount = current['close'] - previous['close']
                            price_change_percent = 0
                            if previous['close'] > 0:
                                price_change_percent = round((change_amount / previous['close']) * 100, 4)
                            
                            # 거래량 변화 계산
                            volume_change = current['volume'] - previous['volume']
                            volume_change_percent = 0
                            if previous['volume'] > 0:
                                volume_change_percent = round((volume_change / previous['volume']) * 100, 4)
                            
                            update_data.append({
                                'time': current['time'],
                                'symbol': symbol,
                                'interval_type': interval_type,
                                'change_amount': Decimal(str(change_amount)),
                                'price_change_percent': Decimal(str(price_change_percent)),
                                'volume_change': int(volume_change),
                                'volume_change_percent': Decimal(str(volume_change_percent)),
                                'previous_close_price': Decimal(str(previous['close']))
                            })
                    
                    # 대량 업데이트 실행 (개별 UPDATE 방식으로 변경)
                    if update_data:
                        update_query = text("""
                            UPDATE stock_prices 
                            SET 
                                change_amount = :change_amount,
                                price_change_percent = :price_change_percent,
                                volume_change = :volume_change,
                                volume_change_percent = :volume_change_percent,
                                previous_close_price = :previous_close_price
                            WHERE time = :time 
                              AND symbol = :symbol 
                              AND interval_type = :interval_type
                        """)
                        
                        # executemany를 사용하여 배치 실행
                        result = await session.execute(update_query, update_data)
                        total_updated += len(update_data)
                    
                    processed_symbols += len(batch_symbols)
                    self.logger.info(f"배치 계산 진행: {processed_symbols}/{len(symbols)} 종목 완료")
                
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                self.logger.info(f"배치 계산 완료: {total_updated}건 업데이트, {duration:.2f}초 소요")
                
                return {
                    "success": True,
                    "total_symbols": len(symbols),
                    "total_updated": total_updated,
                    "duration_seconds": duration,
                    "records_per_second": round(total_updated / duration) if duration > 0 else 0
                }
                
        except Exception as e:
            self.logger.error(f"배치 계산 실패: {e}")
            raise

    async def check_trigger_status(self) -> Dict[str, Any]:
        """트리거 상태 확인 (현재는 모든 트리거 제거됨)"""
        try:
            async with get_timescale_session_context() as session:
                # 트리거 존재 여부 확인
                trigger_check = text("""
                    SELECT COUNT(*) 
                    FROM information_schema.triggers 
                    WHERE trigger_name = 'stock_price_auto_calculation_trigger'
                      AND event_object_table = 'stock_prices'
                """)
                
                result = await session.execute(trigger_check)
                trigger_count = result.scalar() or 0
                
                return {
                    "trigger_exists": trigger_count > 0,
                    "trigger_count": trigger_count,
                    "calculation_method": "배치 계산 방식" if trigger_count == 0 else "트리거 방식",
                    "status": "트리거 제거됨 - 배치 계산만 사용" if trigger_count == 0 else "트리거 활성화"
                }
                
        except Exception as e:
            self.logger.error(f"트리거 상태 확인 실패: {e}")
            return {
                "trigger_exists": None,
                "trigger_count": None,
                "calculation_method": "확인 불가",
                "status": f"오류: {e}"
            }

    async def batch_calculate_for_new_data(
        self,
        symbols: List[str],
        start_date: datetime = None
    ) -> Dict[str, Any]:
        """
        새로 삽입된 데이터에 대한 빠른 배치 계산
        
        Args:
            symbols: 계산할 종목 리스트
            start_date: 계산 시작일 (None이면 최근 7일)
            
        Returns:
            Dict: 계산 결과
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=7)
            
        return await self.batch_calculate_stock_price_changes(
            symbols=symbols,
            days_back=(datetime.utcnow() - start_date).days + 1,
            batch_size=20  # 더 큰 배치로 빠른 처리
        )

    async def bulk_create_stock_prices_with_progress(
        self, 
        prices: List[StockPriceCreate], 
        batch_size: int = 2000,  # 트리거 없음으로 큰 배치 크기 가능
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        주가 데이터 대량 생성 (진행상황 모니터링, 트리거 없음)
        
        Args:
            prices: 주가 데이터 리스트
            batch_size: 배치 크기 (기본값: 2000)
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            Dict: 처리 결과
        """
        await self.initialize()
        
        total_count = len(prices)
        processed_count = 0
        success_count = 0
        error_count = 0
        
        try:
            # 배치 단위로 처리
            for i in range(0, total_count, batch_size):
                batch = prices[i:i + batch_size]
                
                try:
                    # 빠른 INSERT 방식 사용
                    result = await self.bulk_create_stock_prices(BulkStockPriceCreate(prices=batch))
                    if result.get("success"):
                        success_count += len(batch)
                    else:
                        error_count += len(batch)
                        
                except Exception as e:
                    self.logger.error(f"배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                    error_count += len(batch)
                
                processed_count += len(batch)
                
                # 진행상황 알림
                if progress_callback:
                    progress = (processed_count / total_count) * 100
                    await progress_callback(processed_count, total_count, progress, success_count, error_count)
                
                # 메모리 정리를 위한 짧은 대기 (더 짧게 조정)
                await asyncio.sleep(0.01)
            
            self.logger.info(f"주가 데이터 대량 처리 완료: 총 {total_count}건, 성공 {success_count}건, 실패 {error_count}건")
            
            return {
                "success": True,
                "total_count": total_count,
                "success_count": success_count,
                "error_count": error_count,
                "message": f"주가 데이터 대량 처리 완료: 성공 {success_count}건 / 실패 {error_count}건"
            }
            
        except Exception as e:
            self.logger.error(f"주가 데이터 대량 처리 실패: {e}")
            raise

    # ========================================
    # 헬스체크 및 통계 관련 메서드
    # ========================================
    
    async def health_check(self) -> TimescaleHealthCheck:
        """TimescaleDB 헬스체크"""
        try:
            conn_info = await self.connection_monitor.get_connection_info()
            
            if conn_info.get("status") == "healthy":
                # 하이퍼테이블 수 조회 (올바른 컬럼명 사용)
                async with get_timescale_session_context() as session:
                    result = await session.execute(
                        text("SELECT COUNT(*) FROM timescaledb_information.hypertables WHERE hypertable_schema = 'public'")
                    )
                    hypertable_count = result.scalar() or 0
                
                return TimescaleHealthCheck(
                    status="healthy",
                    database_size=conn_info.get("database_size"),
                    active_connections=conn_info.get("active_connections"),
                    hypertable_count=hypertable_count
                )
            else:
                return TimescaleHealthCheck(
                    status="unhealthy",
                    database_size=None,
                    active_connections=None,
                    hypertable_count=None
                )
                
        except Exception as e:
            self.logger.error(f"헬스체크 실패: {e}")
            return TimescaleHealthCheck(
                status="unhealthy",
                database_size=None,
                active_connections=None,
                hypertable_count=None
            )
    
    async def get_statistics(self) -> TimescaleStats:
        """TimescaleDB 통계 조회"""
        try:
            async with get_timescale_session_context() as session:
                # 테이블 크기 조회
                size_query = text("""
                    SELECT 
                        schemaname || '.' || tablename as table_name,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    AND tablename IN ('stock_prices', 'supply_demand', 'realtime_prices', 'market_indices', 'trading_sessions')
                """)
                
                result = await session.execute(size_query)
                table_sizes = {row.table_name: row.size for row in result.fetchall()}
                
                # 청크 수 조회 (올바른 컬럼명 사용)
                chunk_query = text("""
                    SELECT 
                        hypertable_name,
                        num_chunks,
                        compression_enabled
                    FROM timescaledb_information.hypertables
                    WHERE hypertable_schema = 'public'
                """)
                
                result = await session.execute(chunk_query)
                chunk_data = {}
                compression_data = {}
                
                for row in result.fetchall():
                    chunk_data[row.hypertable_name] = row.num_chunks or 0
                    compression_data[row.hypertable_name] = {
                        "total_chunks": row.num_chunks or 0,
                        "compression_enabled": row.compression_enabled or False
                    }
                
                return TimescaleStats(
                    table_sizes=table_sizes,
                    chunk_count=chunk_data,
                    compression_stats=compression_data,
                    query_performance={}  # TODO: 쿼리 성능 메트릭 추가
                )
                
        except Exception as e:
            self.logger.error(f"통계 조회 실패: {e}")
            return TimescaleStats()

    async def optimize_for_bulk_insert(self) -> None:
        """대량 삽입을 위한 데이터베이스 최적화 설정"""
        try:
            async with get_timescale_session_context() as session:
                # 대량 삽입 성능 최적화 설정
                optimization_queries = [
                    # WAL 버퍼 크기 증가 (메모리 내 버퍼링)
                    "SET wal_buffers = '64MB'",
                    # 체크포인트 간격 늘리기 (배치 처리 중 I/O 줄이기)
                    "SET checkpoint_segments = 64",
                    # 커밋 지연 설정 (트랜잭션 그룹화)
                    "SET commit_delay = 10000",
                    # 동기 커밋 비활성화 (성능 우선 - 주의 필요)
                    # "SET synchronous_commit = off",  # 주석 처리 - 데이터 안전성 고려
                    # 병렬 작업자 수 증가
                    "SET max_parallel_workers_per_gather = 4",
                    # 메모리 설정 최적화
                    "SET work_mem = '256MB'",
                    "SET maintenance_work_mem = '512MB'"
                ]
                
                for query in optimization_queries:
                    try:
                        await session.execute(text(query))
                        self.logger.debug(f"최적화 설정 적용: {query}")
                    except Exception as e:
                        self.logger.warning(f"최적화 설정 실패 (무시 가능): {query} - {e}")
                
                self.logger.info("대량 삽입 최적화 설정 완료")
                
        except Exception as e:
            self.logger.error(f"데이터베이스 최적화 설정 실패: {e}")
    
    async def reset_optimization_settings(self) -> None:
        """최적화 설정 원복"""
        try:
            async with get_timescale_session_context() as session:
                # 기본 설정으로 복원
                reset_queries = [
                    "RESET wal_buffers",
                    "RESET checkpoint_segments", 
                    "RESET commit_delay",
                    "RESET max_parallel_workers_per_gather",
                    "RESET work_mem",
                    "RESET maintenance_work_mem"
                ]
                
                for query in reset_queries:
                    try:
                        await session.execute(text(query))
                    except Exception as e:
                        self.logger.warning(f"설정 원복 실패 (무시 가능): {query} - {e}")
                
                self.logger.info("최적화 설정 원복 완료")
                
        except Exception as e:
            self.logger.error(f"설정 원복 실패: {e}")

    async def bulk_create_stock_prices_optimized(self, prices: BulkStockPriceCreate) -> Dict[str, Any]:
        """최고 성능 주가 데이터 대량 생성 (PostgreSQL COPY 사용, 트리거 없음)"""
        await self.initialize()
        
        try:
            # 대량 삽입 최적화 설정 적용
            await self.optimize_for_bulk_insert()
            
            async with get_timescale_session_context() as session:
                # COPY를 사용한 최고 성능 삽입
                import io
                import csv
                
                # CSV 형태로 데이터 준비
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)
                
                current_time = datetime.utcnow()
                for price in prices.prices:
                    price_dict = price.dict()
                    row = [
                        price_dict.get('time', current_time),
                        price_dict.get('symbol', ''),
                        price_dict.get('interval_type', '1d'),
                        price_dict.get('open', None),
                        price_dict.get('high', None),
                        price_dict.get('low', None),
                        price_dict.get('close', None),
                        price_dict.get('volume', None),
                        price_dict.get('trading_value', None),
                        price_dict.get('adjusted_price_type', None),
                        price_dict.get('adjustment_ratio', None),
                        price_dict.get('adjusted_price_event', None),
                        price_dict.get('major_industry_type', None),
                        price_dict.get('minor_industry_type', None),
                        price_dict.get('stock_info', None),
                        current_time
                    ]
                    csv_writer.writerow(row)
                
                # CSV 데이터를 BytesIO로 변환
                csv_data = csv_buffer.getvalue()
                csv_buffer.close()
                
                # COPY 명령으로 고속 삽입
                copy_query = """
                COPY stock_prices (time, symbol, interval_type, open, high, low, close, volume, trading_value,
                                 adjusted_price_type, adjustment_ratio, adjusted_price_event,
                                 major_industry_type, minor_industry_type, stock_info, created_at)
                FROM STDIN WITH CSV
                """
                
                # Raw connection을 통한 COPY 실행
                raw_conn = await session.connection.get_raw_connection()
                async with raw_conn.cursor() as cursor:
                    await cursor.copy_expert(copy_query, io.StringIO(csv_data))
                
                await session.commit()
                
                self.logger.info(f"주가 데이터 {len(prices.prices)}건 고속 삽입 완료 (COPY 사용)")
                
                return {
                    "success": True,
                    "inserted_count": len(prices.prices),
                    "message": f"{len(prices.prices)}건의 주가 데이터가 고속으로 저장되었습니다"
                }
                
        except Exception as e:
            self.logger.error(f"고속 주가 데이터 삽입 실패: {e}")
            # 실패 시 일반 방식으로 폴백
            return await self.bulk_create_stock_prices(prices)
        finally:
            # 최적화 설정 원복
            try:
                await self.reset_optimization_settings()
            except:
                pass


# 전역 서비스 인스턴스
timescale_service = TimescaleService() 