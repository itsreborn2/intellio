"""
ETF 관련 스키마 정의
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field


class ETFComponentData(BaseModel):
    """ETF 구성종목 데이터"""
    symbol: str = Field(..., description="종목 코드")
    name: str = Field(..., description="종목명")
    weight: Decimal = Field(..., description="비중 (%)")
    shares: Optional[int] = Field(None, description="보유 주식 수")
    market_value: Optional[Decimal] = Field(None, description="시가총액")
    sector: Optional[str] = Field(None, description="섹터")


class ETFComponentsResponse(BaseModel):
    """ETF 구성종목 목록 응답"""
    etf_code: str = Field(..., description="ETF 코드")
    etf_name: str = Field(..., description="ETF 명")
    components: List[ETFComponentData] = Field(..., description="구성종목 목록")
    total_count: int = Field(..., description="전체 구성종목 수")
    updated_at: datetime = Field(..., description="업데이트 시간")


class ETFBasicInfo(BaseModel):
    """ETF 기본 정보"""
    etf_code: str = Field(..., description="ETF 코드")
    etf_name: str = Field(..., description="ETF 명")
    nav: Optional[Decimal] = Field(None, description="순자산가치")
    market_price: Optional[Decimal] = Field(None, description="시장가격")
    premium_discount: Optional[Decimal] = Field(None, description="프리미엄/할인율")
    tracking_error: Optional[Decimal] = Field(None, description="추적 오차")
    expense_ratio: Optional[Decimal] = Field(None, description="비용 비율")
    aum: Optional[Decimal] = Field(None, description="운용자산규모")
    benchmark: Optional[str] = Field(None, description="기초지수")
    inception_date: Optional[str] = Field(None, description="설정일")
    updated_at: datetime = Field(..., description="업데이트 시간") 