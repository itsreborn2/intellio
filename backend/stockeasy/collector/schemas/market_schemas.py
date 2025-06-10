"""
시장 관련 스키마 정의
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class MarketStatusResponse(BaseModel):
    """시장 상태 응답"""
    market_code: str = Field(..., description="시장 코드")
    market_name: str = Field(..., description="시장명")
    is_open: bool = Field(..., description="개장 여부")
    open_time: Optional[str] = Field(None, description="개장 시간")
    close_time: Optional[str] = Field(None, description="폐장 시간")
    current_time: datetime = Field(..., description="현재 시간")
    trading_day: str = Field(..., description="거래일")


class MarketIndexData(BaseModel):
    """주요 지수 데이터"""
    index_code: str = Field(..., description="지수 코드")
    index_name: str = Field(..., description="지수명")
    current_value: Decimal = Field(..., description="현재값")
    change_value: Decimal = Field(..., description="변동값")
    change_rate: Decimal = Field(..., description="변동률")
    volume: Optional[int] = Field(None, description="거래량")
    updated_at: datetime = Field(..., description="업데이트 시간")


class MarketIndicesResponse(BaseModel):
    """주요 지수 목록 응답"""
    indices: List[MarketIndexData] = Field(..., description="지수 목록")
    updated_at: datetime = Field(..., description="업데이트 시간")


class TradingCalendarData(BaseModel):
    """거래일 정보"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    is_trading_day: bool = Field(..., description="거래일 여부")
    market_type: str = Field(..., description="시장 구분")
    description: Optional[str] = Field(None, description="설명 (휴장 사유 등)") 