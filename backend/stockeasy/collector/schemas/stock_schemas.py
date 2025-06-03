"""
주식 데이터용 Pydantic 스키마
"""
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel, Field, validator


class StockSymbolBase(BaseModel):
    """종목 기본 정보 베이스"""
    symbol: str = Field(..., description="종목코드", max_length=20)
    name: str = Field(..., description="종목명", max_length=100)
    market: str = Field(..., description="시장구분", max_length=20)
    sector: Optional[str] = Field(None, description="업종", max_length=50)
    listing_date: Optional[date] = Field(None, description="상장일")


class StockSymbolCreate(StockSymbolBase):
    """종목 생성용 스키마"""
    pass


class StockSymbolResponse(StockSymbolBase):
    """종목 응답용 스키마"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StockPriceBase(BaseModel):
    """주가 데이터 베이스"""
    symbol: str = Field(..., description="종목코드", max_length=20)
    name: str = Field(..., description="종목명", max_length=100)
    trade_date: date = Field(..., description="거래일자")
    
    # OHLCV
    open_price: Optional[Decimal] = Field(None, description="시가")
    high_price: Optional[Decimal] = Field(None, description="고가")
    low_price: Optional[Decimal] = Field(None, description="저가")
    close_price: Optional[Decimal] = Field(None, description="종가")
    volume: Optional[int] = Field(None, description="거래량")
    trading_value: Optional[int] = Field(None, description="거래대금")
    
    # 주식 기본정보
    total_shares: Optional[int] = Field(None, description="총주식수")
    market_cap: Optional[int] = Field(None, description="시가총액")
    listed_shares: Optional[int] = Field(None, description="상장주식수")
    floating_shares: Optional[int] = Field(None, description="유통주식수")
    floating_ratio: Optional[Decimal] = Field(None, description="유통비율(%)")


class StockPriceCreate(StockPriceBase):
    """주가 데이터 생성용"""
    pass


class StockPriceResponse(StockPriceBase):
    """주가 데이터 응답용"""
    id: int
    adj_factor: Optional[Decimal]
    adj_close_price: Optional[Decimal]
    per: Optional[Decimal]
    pbr: Optional[Decimal]
    eps: Optional[Decimal]
    bps: Optional[Decimal]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StockSupplyDemandBase(BaseModel):
    """수급 데이터 베이스"""
    symbol: str = Field(..., description="종목코드", max_length=20)
    trade_date: date = Field(..., description="거래일자")
    
    # 수급 데이터
    foreign_net: Optional[int] = Field(None, description="외국인 순매수")
    institution_net: Optional[int] = Field(None, description="기관계 순매수")
    financial_investment_net: Optional[int] = Field(None, description="금융투자 순매수")
    insurance_net: Optional[int] = Field(None, description="보험 순매수")
    investment_trust_net: Optional[int] = Field(None, description="투신 순매수")
    other_financial_net: Optional[int] = Field(None, description="기타금융기관 순매수")
    bank_net: Optional[int] = Field(None, description="은행 순매수")
    pension_net: Optional[int] = Field(None, description="연기금 순매수")
    private_fund_net: Optional[int] = Field(None, description="사모펀드 순매수")
    government_net: Optional[int] = Field(None, description="국가(지자체) 순매수")
    other_corporate_net: Optional[int] = Field(None, description="기타법인 순매수")
    foreign_domestic_net: Optional[int] = Field(None, description="내외국인 순매수")
    program_net: Optional[int] = Field(None, description="프로그램 순매수")


class StockSupplyDemandCreate(StockSupplyDemandBase):
    """수급 데이터 생성용"""
    pass


class StockSupplyDemandResponse(StockSupplyDemandBase):
    """수급 데이터 응답용"""
    id: int
    total_volume: Optional[int]
    foreign_volume: Optional[int]
    institution_volume: Optional[int]
    individual_volume: Optional[int]
    total_value: Optional[int]
    foreign_value: Optional[int]
    institution_value: Optional[int]
    individual_value: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StockRealtimeBase(BaseModel):
    """실시간 데이터 베이스"""
    symbol: str = Field(..., description="종목코드", max_length=20)
    current_price: Optional[Decimal] = Field(None, description="현재가")
    change_amount: Optional[Decimal] = Field(None, description="전일대비 금액")
    change_rate: Optional[Decimal] = Field(None, description="전일대비 비율(%)")
    volume: Optional[int] = Field(None, description="거래량")
    trading_value: Optional[int] = Field(None, description="거래대금")
    bid_price: Optional[Decimal] = Field(None, description="매수호가")
    ask_price: Optional[Decimal] = Field(None, description="매도호가")
    bid_volume: Optional[int] = Field(None, description="매수호가량")
    ask_volume: Optional[int] = Field(None, description="매도호가량")
    day_high: Optional[Decimal] = Field(None, description="당일 고가")
    day_low: Optional[Decimal] = Field(None, description="당일 저가")


class StockRealtimeCreate(StockRealtimeBase):
    """실시간 데이터 생성용"""
    last_update: datetime = Field(..., description="마지막 업데이트")
    trade_time: Optional[datetime] = Field(None, description="체결시간")


class StockRealtimeResponse(StockRealtimeBase):
    """실시간 데이터 응답용"""
    id: int
    last_update: datetime
    trade_time: Optional[datetime]
    
    class Config:
        from_attributes = True


class ChartDataRequest(BaseModel):
    """차트 데이터 요청"""
    symbol: str = Field(..., description="종목코드")
    period: str = Field(default="1d", description="조회 기간 (1d, 1w, 1m, 3m, 6m, 1y)")
    interval: str = Field(default="1m", description="간격 (1m, 5m, 15m, 30m, 1h, 1d)")
    start_date: Optional[date] = Field(None, description="시작일")
    end_date: Optional[date] = Field(None, description="종료일")
    
    @validator('period')
    def validate_period(cls, v):
        allowed_periods = ['1d', '1w', '1m', '3m', '6m', '1y', '2y', '5y']
        if v not in allowed_periods:
            raise ValueError(f'기간은 {allowed_periods} 중 하나여야 합니다')
        return v
    
    @validator('interval')
    def validate_interval(cls, v):
        allowed_intervals = ['1m', '5m', '15m', '30m', '1h', '1d', '1w', '1M']
        if v not in allowed_intervals:
            raise ValueError(f'간격은 {allowed_intervals} 중 하나여야 합니다')
        return v


class ChartDataPoint(BaseModel):
    """차트 데이터 포인트"""
    timestamp: datetime = Field(..., description="시간")
    open: Optional[Decimal] = Field(None, description="시가")
    high: Optional[Decimal] = Field(None, description="고가")
    low: Optional[Decimal] = Field(None, description="저가")
    close: Optional[Decimal] = Field(None, description="종가")
    volume: Optional[int] = Field(None, description="거래량")


class ChartDataResponse(BaseModel):
    """차트 데이터 응답"""
    symbol: str = Field(..., description="종목코드")
    name: str = Field(..., description="종목명")
    period: str = Field(..., description="조회 기간")
    interval: str = Field(..., description="간격")
    data: List[ChartDataPoint] = Field(..., description="차트 데이터")
    total_count: int = Field(..., description="총 데이터 개수")


class StockSearchRequest(BaseModel):
    """종목 검색 요청"""
    query: str = Field(..., description="검색어", min_length=1, max_length=100)
    market: Optional[str] = Field(None, description="시장 필터")
    sector: Optional[str] = Field(None, description="업종 필터")
    limit: int = Field(default=20, description="결과 개수", ge=1, le=100)


class StockSearchResponse(BaseModel):
    """종목 검색 응답"""
    results: List[StockSymbolResponse] = Field(..., description="검색 결과")
    total_count: int = Field(..., description="총 결과 개수")
    query: str = Field(..., description="검색어")


class StockListRequest(BaseModel):
    """종목 목록 요청"""
    market: Optional[str] = Field(None, description="시장 필터")
    sector: Optional[str] = Field(None, description="업종 필터")
    page: int = Field(default=1, description="페이지", ge=1)
    size: int = Field(default=50, description="페이지당 개수", ge=1, le=500)
    sort_by: str = Field(default="symbol", description="정렬 기준")
    sort_order: str = Field(default="asc", description="정렬 순서")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        allowed_fields = ['symbol', 'name', 'market_cap', 'volume', 'change_rate']
        if v not in allowed_fields:
            raise ValueError(f'정렬 기준은 {allowed_fields} 중 하나여야 합니다')
        return v
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError('정렬 순서는 asc 또는 desc여야 합니다')
        return v 