"""
TimescaleDB 전용 서비스 클래스
시계열 데이터의 효율적인 저장 및 조회를 위한 서비스
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal

from sqlalchemy import text, select, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
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

# ✅ 한국 공휴일 체크를 위한 import 추가
from holidayskr import is_holiday


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
                
                # ON CONFLICT를 사용한 upsert - 새로운 필드 구조 반영 (updated_at 포함)
                upsert_query = text("""
                    INSERT INTO stock_prices (time, symbol, interval_type, open, high, low, close, volume, trading_value, 
                                            adjusted_price_type, adjustment_ratio, adjusted_price_event,
                                            major_industry_type, minor_industry_type, stock_info, created_at, updated_at)
                    VALUES (:time, :symbol, :interval_type, :open, :high, :low, :close, :volume, :trading_value,
                           :adjusted_price_type, :adjustment_ratio, :adjusted_price_event,
                           :major_industry_type, :minor_industry_type, :stock_info, :created_at, :updated_at)
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
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at
                """)
                
                # created_at 및 updated_at 필드 추가 및 None 값 처리
                current_time = datetime.utcnow()
                for price_dict in price_dicts:
                    # created_at은 기존 값 유지, updated_at은 항상 현재 UTC 시간으로 강제 갱신
                    if 'created_at' not in price_dict or price_dict['created_at'] is None:
                        price_dict['created_at'] = current_time
                    # updated_at은 기존 값과 관계없이 항상 현재 UTC 시간으로 강제 갱신
                    price_dict['updated_at'] = current_time
                    
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
                                            major_industry_type, minor_industry_type, stock_info, created_at, updated_at)
                    VALUES (:time, :symbol, :interval_type, :open, :high, :low, :close, :volume, :trading_value,
                           :adjusted_price_type, :adjustment_ratio, :adjusted_price_event,
                           :major_industry_type, :minor_industry_type, :stock_info, :created_at, :updated_at)
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
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at
                    RETURNING *
                """)
                
                price_dict = stock_price.dict()
                current_time = datetime.utcnow()
                
                # created_at은 기존 값 유지, updated_at은 항상 현재 UTC 시간으로 강제 갱신
                if 'created_at' not in price_dict or price_dict['created_at'] is None:
                    price_dict['created_at'] = current_time
                # updated_at은 기존 값과 관계없이 항상 현재 UTC 시간으로 강제 갱신
                price_dict['updated_at'] = current_time
                
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
                    self.logger.error(f"배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                    error_count += len(batch)
                
                processed_count += len(batch)
                
                # 진행상황 알림
                if progress_callback:
                    progress = (processed_count / total_count) * 100
                    await progress_callback(processed_count, total_count, progress, success_count, error_count)
                
                # 메모리 정리를 위한 짧은 대기 (더 짧게 조정)
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

    async def batch_calculate_stock_price_changes_optimized(
        self, 
        symbols: List[str] = None,
        days_back: int = 730,  # 2년 전까지 (기본값 복원)
        batch_size: int = 10,  # 더 작은 배치 크기로 안정성 확보
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        안전한 배치 계산 (TimescaleDB 압축 해제 제한 고려)
        
        ⚠️ 중요: LAG() 윈도우 함수는 압축 해제 오류를 유발하므로 사용 금지
        ✅ 2년 전 데이터까지 모두 처리하되 일자별 배치 처리 방식 사용
        
        Args:
            symbols: 계산할 종목 리스트
            days_back: 계산할 일수 (기본 730일 = 2년)
            batch_size: 사용하지 않음 (일자별 처리)
            progress_callback: 진행률 콜백 함수
            
        Returns:
            Dict: 계산 결과
        """
        await self.initialize()
        
        try:
            start_time = datetime.utcnow()
            total_updated = 0
            processed_symbols = 0
            
            # ✅ 2년 전 데이터까지 처리 (기존 요구사항 유지)
            safe_start_date = datetime.now() - timedelta(days=days_back)
            safe_end_date = datetime.now()
            
            # 대상 종목 조회
            async with get_timescale_session_context() as session:
                if symbols is None:
                    symbol_query = text("""
                        SELECT DISTINCT symbol 
                        FROM stock_prices 
                        WHERE time >= :start_date
                          AND time < :end_date
                          AND close IS NOT NULL
                        ORDER BY symbol
                    """)
                    result = await session.execute(symbol_query, {
                        "start_date": safe_start_date,
                        "end_date": safe_end_date
                    })
                    symbols = [row[0] for row in result.fetchall()]
            
            total_symbols = len(symbols)
            self.logger.info(f"안전한 배치 계산 시작: {total_symbols}개 종목, {days_back}일 ({safe_start_date.strftime('%Y-%m-%d')} ~ {safe_end_date.strftime('%Y-%m-%d')})")
            
            # ✅ 일자별 배치 처리 방식 (TIMESCALEDB_SQL_GUIDE.md 권장)
            current_date = safe_start_date.date()
            end_date = safe_end_date.date()
            total_days = (end_date - current_date).days + 1
            processed_days = 0
            
            while current_date <= end_date:
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = day_start + timedelta(days=1)
                
                # ✅ 주말 및 한국 공휴일 체크 (효율성 개선)
                weekday = current_date.weekday()  # 0=월요일, 6=일요일
                if weekday >= 5 or is_holiday(current_date.strftime('%Y-%m-%d')):  # 토요일(5) 또는 일요일(6), 공휴일
                    current_date += timedelta(days=1)
                    continue
                
                self.logger.info(f"일자별 처리: {current_date}")
                
                # 각 종목을 개별 처리
                for symbol in symbols:
                    try:
                        async with get_timescale_session_context() as symbol_session:
                            # 1. 해당 일자의 데이터 조회 (압축 상태 유지)
                            data_query = text("""
                                SELECT time, symbol, interval_type, close, volume
                                FROM stock_prices
                                WHERE symbol = :symbol
                                  AND time >= :day_start
                                  AND time < :day_end
                                  AND close IS NOT NULL
                                  AND close > 0
                                ORDER BY time
                            """)
                            
                            result = await symbol_session.execute(data_query, {
                                "symbol": symbol,
                                "day_start": day_start,
                                "day_end": day_end
                            })
                            data_rows = result.fetchall()
                            
                            if not data_rows:
                                continue
                            
                            # 🔍 해당 일자 데이터 개수 확인
                            #self.logger.info(f"[디버깅] {symbol} {current_date}: 해당 일자 데이터 {len(data_rows)}건 발견")
                            
                            # 2. 이전 일자의 마지막 데이터 조회
                            prev_day_start = day_start - timedelta(days=7)
                            prev_query = text("""
                                SELECT close, volume
                                FROM stock_prices 
                                WHERE symbol = :symbol
                                  AND time >= :prev_day_start
                                  AND time < :day_start
                                  AND close IS NOT NULL
                                  AND close > 0
                                ORDER BY time DESC
                                LIMIT 1
                            """)
                            
                            prev_result = await symbol_session.execute(prev_query, {
                                "symbol": symbol,
                                "prev_day_start": prev_day_start,
                                "day_start": day_start
                            })
                            prev_row = prev_result.fetchone()
                            
                            # 3. 애플리케이션에서 계산 (안전한 방법)
                            prev_close = float(prev_row.close) if prev_row else None
                            prev_volume = prev_row.volume if prev_row else None
                            
                            # 🔍 이전 데이터 조회 결과 디버깅
                            # if prev_row is None:
                            #     self.logger.info(f"[디버깅] {symbol} {current_date}: 이전 일자 데이터 없음 (7일 전부터 조회)")
                            # else:
                            #     self.logger.info(f"[디버깅] {symbol} {current_date}: 이전 데이터 발견 - 종가:{prev_close}, 거래량:{prev_volume}")

                            for i, row in enumerate(data_rows):
                                if i > 0:  # 같은 날 내에서 이전 데이터 사용
                                    prev_close = float(data_rows[i-1].close)
                                    prev_volume = data_rows[i-1].volume
                                
                                # 🔍 prev_close 상태 추적
                                if prev_close is None:
                                    #self.logger.info(f"[디버깅] {symbol} {row.time}: prev_close가 None - 계산 건너뜀")
                                    continue  # 계산할 수 없으므로 다음 레코드로
                                
                                if prev_close is not None:
                                    try:
                                        # 개별 업데이트 (안전한 방식)
                                        change_amount = float(row.close) - prev_close
                                        price_change_percent = round((change_amount / prev_close) * 100, 4) if prev_close > 0 else 0
                                        
                                        volume_change = None
                                        volume_change_percent = None
                                        
                                        # ✅ 거래량 변화율 계산 및 추적
                                        if prev_volume is not None:
                                            volume_change = row.volume - prev_volume
                                            
                                            if prev_volume > 0:
                                                volume_change_percent = round((volume_change / prev_volume) * 100, 4)
                                                
                                                # 🔍 거래량 변화율 0인 케이스 추적
                                                if volume_change_percent == 0:
                                                    if volume_change == 0:
                                                        self.logger.info(f"[거래량추적] {symbol} {row.time}: 거래량 동일 - 현재:{row.volume}, 이전:{prev_volume}")
                                                    else:
                                                        self.logger.info(f"[거래량추적] {symbol} {row.time}: 변화율 반올림으로 0 - 변화량:{volume_change}, 이전:{prev_volume}, 변화율:{(volume_change / prev_volume) * 100:.6f}%")
                                            else:
                                                volume_change_percent = 0
                                                #self.logger.info(f"[거래량추적] {symbol} {row.time}: 이전 거래량 0 - 현재:{row.volume}, 이전:{prev_volume}")
                                        else:
                                            self.logger.info(f"[거래량추적] {symbol} {row.time}: 이전 거래량 None - 현재:{row.volume}")
                                        
                                        # 🔍 NULL 값이 업데이트되는 케이스 추적
                                        if volume_change_percent is None:
                                            self.logger.info(f"[거래량추적] {symbol} {row.time}: volume_change_percent가 None으로 업데이트됨")
                                        
                                        # 강제 업데이트 (COALESCE 제거)
                                        update_query = text("""
                                            UPDATE stock_prices
                                            SET 
                                                previous_close_price = :prev_close,
                                                change_amount = :change_amount,
                                                price_change_percent = :price_change_percent,
                                                volume_change = :volume_change,
                                                volume_change_percent = :volume_change_percent
                                            WHERE time = :time
                                              AND symbol = :symbol
                                              AND interval_type = :interval_type
                                        """)
                                        
                                        await symbol_session.execute(update_query, {
                                            'time': row.time,
                                            'symbol': row.symbol,
                                            'interval_type': row.interval_type,
                                            'prev_close': prev_close,
                                            'change_amount': change_amount,
                                            'price_change_percent': price_change_percent,
                                            'volume_change': volume_change,
                                            'volume_change_percent': volume_change_percent
                                        })
                                        total_updated += 1
                                        
                                    except Exception as update_error:
                                        self.logger.info(f"개별 업데이트 실패 ({symbol}, {row.time}): {update_error}")
                                        continue
                                
                                prev_close = float(row.close)
                                prev_volume = row.volume
                        
                    except Exception as symbol_error:
                        self.logger.error(f"종목 {symbol} 일자 {current_date} 계산 실패: {symbol_error}")
                        continue
                
                # 다음 날로 이동
                current_date += timedelta(days=1)
                processed_days += 1
                
                # 진행률 콜백 호출
                if progress_callback and processed_days % 10 == 0:  # 10일마다 콜백
                    progress = (processed_days / total_days) * 100
                    await progress_callback(processed_days, total_days, progress, total_updated)
                
                # 진행률 로깅
                if processed_days % 30 == 0:  # 30일마다 로깅
                    progress = (processed_days / total_days) * 100
                    self.logger.info(f"진행률: {progress:.1f}% ({processed_days}/{total_days}일)")
                
                # 일자별 처리 간 잠시 대기 (DB 부하 분산)
                await asyncio.sleep(0.01)
            
            # 최종 통계
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.info(
                f"안전한 배치 계산 완료: {total_updated}건 업데이트, "
                f"{total_symbols}개 종목, {processed_days}일 처리, {duration:.2f}초 소요"
            )
            
            return {
                "success": True,
                "method": "일자별 배치 계산 (2년 전 데이터까지)",
                "total_symbols_processed": total_symbols,
                "total_days_processed": processed_days,
                "total_updated": total_updated,
                "batch_size": "일자별",
                "duration_seconds": duration,
                "records_per_second": round(total_updated / duration) if duration > 0 else 0,
                "safety_improvements": "LAG 윈도우 함수 제거, 일자별 배치 처리, 2년 전 데이터까지 처리"
            }
            
        except Exception as e:
            self.logger.error(f"안전한 배치 계산 실패: {e}")
            raise

    async def batch_calculate_stock_price_changes(
        self, 
        symbols: List[str] = None,
        days_back: int = 30,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        주가 데이터 변동률 배치 계산 (TimescaleDB 안전 모드)
        
        TimescaleDB 압축 해제 제한을 고려하여 안전한 처리 방식 사용
        """
       
        
        # 안전한 최적화 메서드로 위임
        return await self.batch_calculate_stock_price_changes_optimized(
            symbols=symbols,
            days_back=days_back,
            batch_size=batch_size,  # 개별 처리로 안정성 확보
            progress_callback=None
        )

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
        새로 추가된 데이터에 대한 안전한 배치 계산
        
        TimescaleDB 튜플 압축 해제 제한을 고려하여 일자별 배치 처리
        ⚠️ LAG() 윈도우 함수는 압축 해제 오류를 유발하므로 사용 금지
        ✅ 2년 전 데이터까지 모두 처리하되 일자별로 나누어 안전하게 처리
        """
        await self.initialize()
        
        try:
            if not start_date:
                # 기본적으로 2년 전부터 처리 (기존 로직 유지)
                start_date = datetime.now() - timedelta(days=730)
            
            self.logger.info(f"새 데이터 배치 계산 시작: {len(symbols)}개 종목, {start_date.strftime('%Y-%m-%d')} 이후")
            
            total_updated = 0
            
            # ✅ 안전한 방식: 일자별 배치 처리 (TIMESCALEDB_SQL_GUIDE.md 권장)
            # 전체 기간을 일자별로 나누어 처리
            current_date = start_date.date()
            end_date = datetime.now().date()
            
            while current_date <= end_date:
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = day_start + timedelta(days=1)
                
                # ✅ 주말 및 한국 공휴일 체크 (효율성 개선)
                weekday = current_date.weekday()  # 0=월요일, 6=일요일
                if weekday >= 5 or is_holiday(current_date.strftime('%Y-%m-%d')):  # 토요일(5) 또는 일요일(6)
                    #self.logger.info(f"주말 건너뜀: {current_date} ({'토요일' if weekday == 5 else '일요일'})")
                    current_date += timedelta(days=1)
                    continue
                
                self.logger.info(f"일자별 처리: {current_date}")
                
                # 각 종목을 개별 처리
                for symbol in symbols:
                    try:
                        async with get_timescale_session_context() as session:
                            # 1. 해당 일자의 데이터 조회 (압축 상태 유지)
                            data_query = text("""
                                SELECT time, symbol, interval_type, close, volume
                                FROM stock_prices 
                                WHERE symbol = :symbol
                                  AND time >= :day_start
                                  AND time < :day_end
                                  AND close IS NOT NULL
                                  AND close > 0
                                ORDER BY time
                            """)
                            
                            result = await session.execute(data_query, {
                                "symbol": symbol,
                                "day_start": day_start,
                                "day_end": day_end
                            })
                            data_rows = result.fetchall()
                            
                            if not data_rows:
                                continue
                            
                            # 🔍 해당 일자 데이터 개수 확인
                            #self.logger.info(f"[디버깅] {symbol} {current_date}: 해당 일자 데이터 {len(data_rows)}건 발견")
                            
                            # 2. 이전 일자의 마지막 데이터 조회 (전일종가용)
                            prev_day_start = day_start - timedelta(days=7)  # 7일 전까지 조회
                            prev_query = text("""
                                SELECT close, volume
                                FROM stock_prices 
                                WHERE symbol = :symbol
                                  AND time >= :prev_day_start
                                  AND time < :day_start
                                  AND close IS NOT NULL
                                  AND close > 0
                                ORDER BY time DESC
                                LIMIT 1
                            """)
                            
                            prev_result = await session.execute(prev_query, {
                                "symbol": symbol,
                                "prev_day_start": prev_day_start,
                                "day_start": day_start
                            })
                            prev_row = prev_result.fetchone()
                            
                            # 3. 애플리케이션에서 계산 (안전한 방법)
                            prev_close = float(prev_row.close) if prev_row else None
                            prev_volume = prev_row.volume if prev_row else None
                            
                            # 🔍 이전 데이터 조회 결과 디버깅
                            # if prev_row is None:
                            #     self.logger.info(f"[디버깅] {symbol} {current_date}: 이전 일자 데이터 없음 (7일 전부터 조회)")
                            # else:
                            #     self.logger.info(f"[디버깅] {symbol} {current_date}: 이전 데이터 발견 - 종가:{prev_close}, 거래량:{prev_volume}")

                            for i, row in enumerate(data_rows):
                                if i > 0:  # 같은 날 내에서 이전 데이터 사용
                                    prev_close = float(data_rows[i-1].close)
                                    prev_volume = data_rows[i-1].volume
                                
                                # 🔍 prev_close 상태 추적
                                if prev_close is None:
                                    #self.logger.info(f"[디버깅] {symbol} {row.time}: prev_close가 None - 계산 건너뜀")
                                    continue  # 계산할 수 없으므로 다음 레코드로
                                
                                if prev_close is not None:
                                    try:
                                        # 변동률 계산
                                        change_amount = float(row.close) - prev_close
                                        price_change_percent = round((change_amount / prev_close) * 100, 4) if prev_close > 0 else 0
                                        
                                        volume_change = None
                                        volume_change_percent = None
                                        if prev_volume is not None:
                                            volume_change = row.volume - prev_volume
                                            volume_change_percent = round((volume_change / prev_volume) * 100, 4) if prev_volume > 0 else 0
                                        
                                        # 개별 업데이트 (강제 업데이트 모드)
                                        update_query = text("""
                                            UPDATE stock_prices
                                            SET 
                                                previous_close_price = :prev_close,
                                                change_amount = :change_amount,
                                                price_change_percent = :price_change_percent,
                                                volume_change = :volume_change,
                                                volume_change_percent = :volume_change_percent
                                            WHERE time = :time
                                              AND symbol = :symbol
                                              AND interval_type = :interval_type
                                        """)
                                        
                                        await session.execute(update_query, {
                                            'time': row.time,
                                            'symbol': row.symbol,
                                            'interval_type': row.interval_type,
                                            'prev_close': prev_close,
                                            'change_amount': change_amount,
                                            'price_change_percent': price_change_percent,
                                            'volume_change': volume_change,
                                            'volume_change_percent': volume_change_percent
                                        })

                                        total_updated += 1
                                        #self.logger.info(f"volume_change_percent: {volume_change_percent}")
                                        
                                    except Exception as update_error:
                                        self.logger.info(f"개별 업데이트 실패 ({symbol}, {row.time}): {update_error}")
                                        continue
                                
                                # 다음 루프를 위해 현재 값 저장
                                prev_close = float(row.close)
                                prev_volume = row.volume
                            
                    except Exception as symbol_error:
                        self.logger.error(f"종목 {symbol} 일자 {current_date} 계산 실패: {symbol_error}")
                        continue
                
                # 다음 날로 이동
                current_date += timedelta(days=1)
                
                # 일자별 처리 간 잠시 대기 (DB 부하 분산)
                await asyncio.sleep(0.01)
            
            self.logger.info(f"새 데이터 배치 계산 완료: 총 {total_updated}건 업데이트")
            return {
                "success": True,
                "total_updated": total_updated,
                "processed_symbols": len(symbols),
                "start_date": start_date.isoformat(),
                "method": "일자별 배치 처리 (2년 전 데이터까지)"
            }
            
        except Exception as e:
            self.logger.error(f"새 데이터 배치 계산 실패: {e}")
            raise

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
                        self.logger.info(f"최적화 설정 적용: {query}")
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

    async def upsert_today_stock_prices(
        self, 
        prices: List[StockPriceCreate],
        target_date: datetime,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        당일 주가 데이터 UPSERT (수정주가 정보 보존)
        DELETE 없이 순수 UPSERT 방식으로 수정주가 정보는 유지하면서 OHLCV만 업데이트
        
        Args:
            prices: 주가 데이터 리스트
            target_date: 대상 날짜
            batch_size: 배치 크기
            
        Returns:
            Dict: 처리 결과
        """
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                target_date_str = target_date.strftime('%Y-%m-%d')
                
                symbols_to_update = list(set([price.symbol for price in prices]))
                total_upserted = 0
                current_time = datetime.utcnow()
                
                self.logger.info(f"당일 주가 데이터 UPSERT 시작 (수정주가 보존): {target_date_str}, {len(symbols_to_update)}개 종목")
                
                for i in range(0, len(prices), batch_size):
                    batch_prices = prices[i:i + batch_size]
                    
                    # 배치 UPSERT를 위한 데이터 준비
                    price_dicts = []
                    for price in batch_prices:
                        price_dict = price.dict()
                        price_dict['created_at'] = current_time
                        # updated_at 필드 설정 (StockPriceCreate에서 제공된 값 사용, 없으면 현재 시간)
                        if 'updated_at' not in price_dict or price_dict['updated_at'] is None:
                            price_dict['updated_at'] = current_time
                        # 새로운 필드들에 대한 기본값 설정
                        for field in ['adjusted_price_type', 'adjustment_ratio', 'adjusted_price_event',
                                    'major_industry_type', 'minor_industry_type', 'stock_info']:
                            if field not in price_dict:
                                price_dict[field] = None
                        price_dicts.append(price_dict)
                    
                    # 수정주가 정보 보존하는 UPSERT 쿼리 (기존 값 우선)
                    upsert_query = text("""
                        INSERT INTO stock_prices (time, symbol, interval_type, open, high, low, close, volume, trading_value, 
                                                change_amount, price_change_percent, volume_change, volume_change_percent, previous_close_price,
                                                adjusted_price_type, adjustment_ratio, adjusted_price_event,
                                                major_industry_type, minor_industry_type, stock_info, created_at, updated_at)
                        VALUES (:time, :symbol, :interval_type, :open, :high, :low, :close, :volume, :trading_value,
                               :change_amount, :price_change_percent, :volume_change, :volume_change_percent, :previous_close_price,
                               :adjusted_price_type, :adjustment_ratio, :adjusted_price_event,
                               :major_industry_type, :minor_industry_type, :stock_info, :created_at, :updated_at)
                        ON CONFLICT (time, symbol, interval_type) 
                        DO UPDATE SET
                            -- OHLCV 및 변동률 정보는 무조건 업데이트 (ka10095 실시간 데이터)
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            trading_value = EXCLUDED.trading_value,
                            change_amount = EXCLUDED.change_amount,
                            price_change_percent = EXCLUDED.price_change_percent,
                            volume_change = EXCLUDED.volume_change,
                            volume_change_percent = EXCLUDED.volume_change_percent,
                            previous_close_price = EXCLUDED.previous_close_price,
                            -- 수정주가 정보는 기존 값을 우선 보존 (기존 값이 있으면 그대로, 없으면 새 값)
                            adjusted_price_type = COALESCE(stock_prices.adjusted_price_type, EXCLUDED.adjusted_price_type),
                            adjustment_ratio = COALESCE(stock_prices.adjustment_ratio, EXCLUDED.adjustment_ratio),
                            adjusted_price_event = COALESCE(stock_prices.adjusted_price_event, EXCLUDED.adjusted_price_event),
                            -- 기타 필드도 기존 값 우선 보존
                            major_industry_type = COALESCE(stock_prices.major_industry_type, EXCLUDED.major_industry_type),
                            minor_industry_type = COALESCE(stock_prices.minor_industry_type, EXCLUDED.minor_industry_type),
                            stock_info = COALESCE(stock_prices.stock_info, EXCLUDED.stock_info),
                            -- 업데이트 시간 갱신
                            created_at = EXCLUDED.created_at,
                            updated_at = EXCLUDED.updated_at
                    """)
                    
                    await session.execute(upsert_query, price_dicts)
                    total_upserted += len(price_dicts)
                    
                    self.logger.info(f"당일 데이터 배치 UPSERT (수정주가 보존): {len(price_dicts)}건")
                
                self.logger.info(f"당일 주가 데이터 UPSERT 완료 (수정주가 보존): {target_date_str}, 총 {total_upserted}건")
                
                return {
                    "success": True,
                    "target_date": target_date_str,
                    "symbols_updated": len(symbols_to_update),
                    "total_upserted": total_upserted,
                    "message": f"{target_date_str} 주가 데이터 {total_upserted}건 UPSERT 완료 (수정주가 정보 보존)"
                }
                
        except Exception as e:
            self.logger.error(f"당일 주가 데이터 UPSERT 실패 (수정주가 보존): {e}")
            raise

    async def upsert_today_stock_prices_preserve_adjustments(
        self, 
        prices: List[StockPriceCreate],
        target_date: datetime,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        당일 주가 데이터 UPSERT (수정주가 필드 보존)
        실시간 데이터 업데이트 시 기존 수정주가 정보를 보존하면서 OHLCV 및 변동률 정보만 업데이트
        
        Args:
            prices: 주가 데이터 리스트
            target_date: 대상 날짜
            batch_size: 배치 크기
            
        Returns:
            Dict: 처리 결과
        """
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                target_date_str = target_date.strftime('%Y-%m-%d')
                total_upserted = 0
                current_time = datetime.utcnow()
                
                for i in range(0, len(prices), batch_size):
                    batch_prices = prices[i:i + batch_size]
                    
                    # 배치 UPSERT를 위한 데이터 준비
                    price_dicts = []
                    for price in batch_prices:
                        price_dict = price.dict()
                        price_dict['created_at'] = current_time
                        # updated_at 필드 설정 (StockPriceCreate에서 제공된 값 사용, 없으면 현재 시간)
                        if 'updated_at' not in price_dict or price_dict['updated_at'] is None:
                            price_dict['updated_at'] = current_time
                        price_dicts.append(price_dict)
                    
                    # 수정주가 필드 보존 UPSERT 쿼리
                    upsert_query = text("""
                        INSERT INTO stock_prices (
                            time, symbol, interval_type, open, high, low, close, volume, trading_value, 
                            change_amount, price_change_percent, volume_change, volume_change_percent, previous_close_price,
                            adjusted_price_type, adjustment_ratio, adjusted_price_event,
                            major_industry_type, minor_industry_type, stock_info, created_at, updated_at
                        )
                        VALUES (
                            :time, :symbol, :interval_type, :open, :high, :low, :close, :volume, :trading_value,
                            :change_amount, :price_change_percent, :volume_change, :volume_change_percent, :previous_close_price,
                            :adjusted_price_type, :adjustment_ratio, :adjusted_price_event,
                            :major_industry_type, :minor_industry_type, :stock_info, :created_at, :updated_at
                        )
                        ON CONFLICT (time, symbol, interval_type) 
                        DO UPDATE SET
                            -- OHLCV 및 변동률 정보만 업데이트 (ka10095에서 제공하는 실시간 정보)
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            trading_value = EXCLUDED.trading_value,
                            change_amount = EXCLUDED.change_amount,
                            price_change_percent = EXCLUDED.price_change_percent,
                            volume_change = EXCLUDED.volume_change,
                            volume_change_percent = EXCLUDED.volume_change_percent,
                            previous_close_price = EXCLUDED.previous_close_price,
                            -- 수정주가 필드는 기존 값 보존 (NULL인 경우에만 새 값 사용)
                            adjusted_price_type = COALESCE(stock_prices.adjusted_price_type, EXCLUDED.adjusted_price_type),
                            adjustment_ratio = COALESCE(stock_prices.adjustment_ratio, EXCLUDED.adjustment_ratio),
                            adjusted_price_event = COALESCE(stock_prices.adjusted_price_event, EXCLUDED.adjusted_price_event),
                            -- 기타 필드도 기존 값 보존
                            major_industry_type = COALESCE(stock_prices.major_industry_type, EXCLUDED.major_industry_type),
                            minor_industry_type = COALESCE(stock_prices.minor_industry_type, EXCLUDED.minor_industry_type),
                            stock_info = COALESCE(stock_prices.stock_info, EXCLUDED.stock_info),
                            -- 업데이트 시간 갱신
                            created_at = EXCLUDED.created_at,
                            updated_at = EXCLUDED.updated_at
                    """)
                    
                    await session.execute(upsert_query, price_dicts)
                    total_upserted += len(price_dicts)
                    
                    self.logger.info(f"당일 데이터 배치 UPSERT (수정주가 보존): {len(price_dicts)}건")
                
                self.logger.info(f"당일 주가 데이터 UPSERT 완료 (수정주가 보존): {target_date_str}, 총 {total_upserted}건")
                
                return {
                    "success": True,
                    "target_date": target_date_str,
                    "total_upserted": total_upserted,
                    "message": f"{target_date_str} 주가 데이터 {total_upserted}건 업데이트 완료 (수정주가 보존)"
                }
                
        except Exception as e:
            self.logger.error(f"당일 주가 데이터 UPSERT 실패 (수정주가 보존): {e}")
            raise


    async def delete_stock_prices_by_symbol_period(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        특정 종목의 기간별 주가 데이터 삭제
        
        Args:
            symbol: 종목 코드
            start_date: 시작 날짜
            end_date: 종료 날짜
            
        Returns:
            Dict: 삭제 결과
        """
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                delete_query = text("""
                    DELETE FROM stock_prices 
                    WHERE symbol = :symbol 
                    AND time >= :start_date 
                    AND time <= :end_date
                """)
                
                result = await session.execute(delete_query, {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                deleted_count = result.rowcount
                self.logger.info(f"주가 데이터 삭제 완료: {symbol}, {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}, {deleted_count}건")
                
                return {
                    "success": True,
                    "symbol": symbol,
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d'),
                    "deleted_count": deleted_count,
                    "message": f"{symbol} 주가 데이터 {deleted_count}건 삭제 완료"
                }
                
        except Exception as e:
            self.logger.error(f"주가 데이터 삭제 실패 ({symbol}): {e}")
            raise

    async def delete_supply_demand_by_symbol_period(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        특정 종목의 기간별 수급 데이터 삭제
        
        Args:
            symbol: 종목 코드
            start_date: 시작 날짜
            end_date: 종료 날짜
            
        Returns:
            Dict: 삭제 결과
        """
        await self.initialize()
        
        try:
            async with get_timescale_session_context() as session:
                delete_query = text("""
                    DELETE FROM supply_demand 
                    WHERE symbol = :symbol 
                    AND date >= :start_date 
                    AND date <= :end_date
                """)
                
                result = await session.execute(delete_query, {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                deleted_count = result.rowcount
                self.logger.info(f"수급 데이터 삭제 완료: {symbol}, {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}, {deleted_count}건")
                
                return {
                    "success": True,
                    "symbol": symbol,
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d'),
                    "deleted_count": deleted_count,
                    "message": f"{symbol} 수급 데이터 {deleted_count}건 삭제 완료"
                }
                
        except Exception as e:
            self.logger.error(f"수급 데이터 삭제 실패 ({symbol}): {e}")
            raise


# 전역 서비스 인스턴스
timescale_service = TimescaleService() 