"""
TimescaleDB용 Pydantic 스키마 정의
입력 검증 및 API 응답을 위한 스키마들
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator, ConfigDict


# 열거형 정의
class IntervalType(str, Enum):
    """차트 간격 타입"""
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class MarketStatus(str, Enum):
    """시장 상태"""
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    PRE_MARKET = "PRE_MARKET"
    AFTER_MARKET = "AFTER_MARKET"
    HOLIDAY = "HOLIDAY"


class SessionType(str, Enum):
    """거래 세션 타입"""
    MARKET_OPEN = "MARKET_OPEN"
    MARKET_CLOSE = "MARKET_CLOSE"
    PRE_MARKET = "PRE_MARKET"
    AFTER_MARKET = "AFTER_MARKET"
    LUNCH_BREAK = "LUNCH_BREAK"


# ========================================
# 주가 데이터 스키마
# ========================================

class StockPriceBase(BaseModel):
    """주가 데이터 기본 스키마"""
    symbol: str = Field(..., max_length=10, description="종목코드")
    interval_type: IntervalType = Field(default=IntervalType.ONE_MINUTE, description="봉 타입")
    open: Optional[Decimal] = Field(None, ge=0, description="시가")
    high: Optional[Decimal] = Field(None, ge=0, description="고가")
    low: Optional[Decimal] = Field(None, ge=0, description="저가")
    close: Optional[Decimal] = Field(None, ge=0, description="종가(현재가)")
    volume: Optional[int] = Field(None, ge=0, description="거래량")
    trading_value: Optional[int] = Field(None, ge=0, description="거래대금")
    
    # 변동 정보 (자동계산)
    change_amount: Optional[Decimal] = Field(None, description="전일대비 변동금액")
    price_change_percent: Optional[Decimal] = Field(None, ge=-100, le=100, description="전일대비 등락율(%)")
    volume_change: Optional[int] = Field(None, description="전일대비 거래량 변화")
    volume_change_percent: Optional[Decimal] = Field(None, description="전일대비 거래량 증감율(%)")
    
    # 기준가 정보 (자동계산)
    previous_close_price: Optional[Decimal] = Field(None, ge=0, description="전일종가")
    
    # 수정주가 관련 정보
    adjusted_price_type: Optional[str] = Field(None, max_length=20, description="수정주가구분")
    adjustment_ratio: Optional[Decimal] = Field(None, description="수정비율")
    adjusted_price_event: Optional[str] = Field(None, max_length=100, description="수정주가이벤트")
    
    # 업종 분류
    major_industry_type: Optional[str] = Field(None, max_length=20, description="대업종구분")
    minor_industry_type: Optional[str] = Field(None, max_length=20, description="소업종구분")
    
    # 추가 정보
    stock_info: Optional[str] = Field(None, max_length=100, description="종목정보")
    
    # 업데이트 시간 (UPSERT 시 갱신)
    updated_at: Optional[datetime] = Field(None, description="업데이트 시간 (UTC)")

    @validator('symbol')
    def validate_symbol(cls, v):
        # 업종 지수 허용 (KOSPI, KOSDAQ)
        if v in ['KOSPI', 'KOSDAQ']:
            return v
        # 일반 종목코드는 6자리 숫자
        if not v.isdigit() or len(v) != 6:
            raise ValueError('종목코드는 6자리 숫자 또는 업종지수(KOSPI, KOSDAQ)여야 합니다')
        return v


class StockPriceCreate(StockPriceBase):
    """주가 데이터 생성 스키마"""
    time: datetime = Field(..., description="시간 (UTC)")


class StockPriceUpdate(BaseModel):
    """주가 데이터 업데이트 스키마"""
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[int] = None
    trading_value: Optional[int] = None
    # 변동 정보는 자동계산되므로 업데이트 스키마에서 제외
    adjusted_price_type: Optional[str] = None
    adjustment_ratio: Optional[Decimal] = None
    adjusted_price_event: Optional[str] = None
    major_industry_type: Optional[str] = None
    minor_industry_type: Optional[str] = None
    stock_info: Optional[str] = None


class StockPriceResponse(StockPriceBase):
    """주가 데이터 응답 스키마"""
    time: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ========================================
# 수급 데이터 스키마  
# ========================================

class SupplyDemandBase(BaseModel):
    """수급 데이터 기본 스키마 (키움 API ka10059 - 종목별투자자기관별)"""
    symbol: str = Field(..., max_length=10, description="종목코드")
    
    # 현재가 정보
    current_price: Optional[Decimal] = Field(None, ge=0, description="현재가")
    price_change_sign: Optional[str] = Field(None, max_length=5, description="대비기호")
    price_change: Optional[Decimal] = Field(None, description="전일대비")
    price_change_percent: Optional[Decimal] = Field(None, description="등락율(%)")
    
    # 거래 정보
    accumulated_volume: Optional[int] = Field(None, ge=0, description="누적거래량")
    accumulated_value: Optional[int] = Field(None, ge=0, description="누적거래대금")
    
    # 투자자별 수급 데이터 (단위: 원 또는 주)
    individual_investor: Optional[int] = Field(None, description="개인투자자")
    foreign_investor: Optional[int] = Field(None, description="외국인투자자")
    institution_total: Optional[int] = Field(None, description="기관계")
    
    # 기관 세부 분류
    financial_investment: Optional[int] = Field(None, description="금융투자")
    insurance: Optional[int] = Field(None, description="보험")
    investment_trust: Optional[int] = Field(None, description="투신")
    other_financial: Optional[int] = Field(None, description="기타금융")
    bank: Optional[int] = Field(None, description="은행")
    pension_fund: Optional[int] = Field(None, description="연기금등")
    private_fund: Optional[int] = Field(None, description="사모펀드")
    
    # 기타 분류
    government: Optional[int] = Field(None, description="국가")
    other_corporation: Optional[int] = Field(None, description="기타법인")
    domestic_foreign: Optional[int] = Field(None, description="내외국인")

    @validator('symbol')
    def validate_symbol(cls, v):
        # 업종 지수 허용 (KOSPI, KOSDAQ)
        if v in ['KOSPI', 'KOSDAQ']:
            return v
        # 일반 종목코드는 6자리 숫자
        if not v.isdigit() or len(v) != 6:
            raise ValueError('종목코드는 6자리 숫자 또는 업종지수(KOSPI, KOSDAQ)여야 합니다')
        return v


class SupplyDemandCreate(SupplyDemandBase):
    """수급 데이터 생성 스키마"""
    date: datetime = Field(..., description="날짜")


class SupplyDemandResponse(SupplyDemandBase):
    """수급 데이터 응답 스키마"""
    date: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ========================================
# 시장 지수 스키마
# ========================================

class MarketIndexBase(BaseModel):
    """시장 지수 기본 스키마"""
    index_code: str = Field(..., max_length=20, description="지수 코드")
    index_value: Decimal = Field(..., ge=0, description="지수 값")
    change_amount: Optional[Decimal] = Field(None, description="전일대비 변동")
    price_change_percent: Optional[Decimal] = Field(None, ge=-100, le=100, description="전일대비 변동률(%)")
    volume: Optional[int] = Field(None, ge=0, description="거래량")
    trading_value: Optional[int] = Field(None, ge=0, description="거래대금")
    rise_count: Optional[int] = Field(None, ge=0, description="상승 종목 수")
    fall_count: Optional[int] = Field(None, ge=0, description="하락 종목 수")
    unchanged_count: Optional[int] = Field(None, ge=0, description="보합 종목 수")

    @validator('index_code')
    def validate_index_code(cls, v):
        if not v or len(v) > 20:
            raise ValueError('지수 코드는 20자 이내여야 합니다')
        return v


class MarketIndexCreate(MarketIndexBase):
    """시장 지수 생성 스키마"""
    time: datetime = Field(..., description="시간 (UTC)")


class MarketIndexResponse(MarketIndexBase):
    """시장 지수 응답 스키마"""
    time: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ========================================
# 거래 세션 스키마
# ========================================

class TradingSessionBase(BaseModel):
    """거래 세션 기본 스키마"""
    market: str = Field(..., max_length=20, description="시장 (KOSPI, KOSDAQ)")
    session_type: SessionType = Field(..., description="세션 타입")
    session_status: str = Field(..., max_length=20, description="세션 상태")
    total_volume: Optional[int] = Field(None, ge=0, description="총 거래량")
    total_value: Optional[int] = Field(None, ge=0, description="총 거래대금")
    listed_count: Optional[int] = Field(None, ge=0, description="상장 종목 수")
    trading_count: Optional[int] = Field(None, ge=0, description="거래 종목 수")
    meta_info: Optional[Dict[str, Any]] = Field(None, description="추가 정보")


class TradingSessionCreate(TradingSessionBase):
    """거래 세션 생성 스키마"""
    time: datetime = Field(..., description="시간 (UTC)")


class TradingSessionResponse(TradingSessionBase):
    """거래 세션 응답 스키마"""
    time: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ========================================
# 복합 조회 및 집계 스키마
# ========================================

class PriceRange(BaseModel):
    """가격 범위 스키마"""
    start_date: datetime = Field(..., description="시작 날짜")
    end_date: datetime = Field(..., description="종료 날짜")
    symbol: Optional[str] = Field(None, description="종목코드 (선택)")
    interval_type: Optional[IntervalType] = Field(None, description="간격 타입 (선택)")


class CandleData(BaseModel):
    """캔들 데이터 스키마"""
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    price_change_percent: Optional[Decimal] = None


class CandleResponse(BaseModel):
    """캔들 차트 응답 스키마"""
    symbol: str
    interval_type: IntervalType
    data: List[CandleData]
    total_count: int
    start_date: datetime
    end_date: datetime


class BulkStockPriceCreate(BaseModel):
    """주가 데이터 대량 생성 스키마"""
    prices: List[StockPriceCreate] = Field(..., min_items=1, max_items=10000, description="주가 데이터 목록")


class BulkSupplyDemandCreate(BaseModel):
    """수급 데이터 대량 생성 스키마"""
    supply_demands: List[SupplyDemandCreate] = Field(..., min_items=1, max_items=1000, description="수급 데이터 목록")


class TimescaleHealthCheck(BaseModel):
    """TimescaleDB 헬스체크 응답 스키마"""
    status: str = Field(..., description="상태 (healthy/unhealthy)")
    database_size: Optional[str] = Field(None, description="데이터베이스 크기")
    active_connections: Optional[int] = Field(None, description="활성 연결 수")
    compression_ratio: Optional[float] = Field(None, description="압축률")
    hypertable_count: Optional[int] = Field(None, description="하이퍼테이블 수")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="마지막 확인 시간")


class TimescaleStats(BaseModel):
    """TimescaleDB 통계 스키마"""
    table_sizes: Dict[str, str] = Field(default_factory=dict, description="테이블별 크기")
    chunk_count: Dict[str, int] = Field(default_factory=dict, description="테이블별 청크 수")
    compression_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="압축 통계")
    query_performance: Dict[str, float] = Field(default_factory=dict, description="쿼리 성능")


# ========================================
# 에러 응답 스키마
# ========================================

class TimescaleError(BaseModel):
    """TimescaleDB 에러 응답 스키마"""
    error_code: str = Field(..., description="에러 코드")
    error_message: str = Field(..., description="에러 메시지")
    details: Optional[Dict[str, Any]] = Field(None, description="상세 정보")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="에러 발생 시간")
    request_id: Optional[str] = Field(None, description="요청 ID") 