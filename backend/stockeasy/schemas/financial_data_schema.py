"""
재무 데이터 API 스키마

이 모듈은 재무 데이터 API의 요청/응답 스키마를 정의합니다.
"""
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from datetime import date, datetime
from pydantic import BaseModel, Field, validator
from decimal import Decimal


class PeriodType(str, Enum):
    """재무 기간 유형"""
    ANNUAL = "annual"
    QUARTERLY = "quarterly"


class IndicatorGroupOut(BaseModel):
    """지표 그룹 응답 모델"""
    code: str
    name: str
    description: Optional[str] = None
    order: int
    
    class Config:
        from_attributes = True


class IndicatorDefinitionOut(BaseModel):
    """지표 정의 응답 모델"""
    code: str
    name: str
    group_code: str
    description: Optional[str] = None
    data_type: str
    unit: Optional[str] = None
    is_standardized: bool = False
    is_core: bool = False
    
    class Config:
        from_attributes = True


class FinancialPeriodOut(BaseModel):
    """재무 기간 응답 모델"""
    id: int
    period_type: str
    year: int
    quarter: Optional[int] = None
    start_date: date
    end_date: date
    
    class Config:
        from_attributes = True


class CompanyBasicInfo(BaseModel):
    """회사 기본 정보"""
    ticker_symbol: str
    name: str
    market_cap: Optional[float] = None
    sector_name: Optional[str] = None
    industry_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class CompanyQueryParams(BaseModel):
    """회사 쿼리 매개변수"""
    sector_code: Optional[str] = None
    industry_code: Optional[str] = None
    search: Optional[str] = None
    skip: Optional[int] = 0
    limit: Optional[int] = 20
    sort_by: Optional[str] = "market_cap"
    sort_asc: Optional[bool] = False


class CompanyListResponse(BaseModel):
    """회사 목록 응답"""
    items: List[CompanyBasicInfo]
    total: int
    page: int
    page_size: int
    total_pages: int


class FinancialDataSearchParams(BaseModel):
    """재무 데이터 검색 매개변수"""
    ticker_symbols: List[str] = Field(..., min_items=1, max_items=10)
    indicator_codes: List[str] = Field(..., min_items=1, max_items=20)
    period_type: PeriodType = PeriodType.ANNUAL
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    quarters: Optional[List[int]] = None
    
    @validator("quarters")
    def validate_quarters(cls, v):
        if v is not None:
            for q in v:
                if q not in [1, 2, 3, 4]:
                    raise ValueError("분기는 1, 2, 3, 4 중 하나여야 합니다")
        return v


class FinancialDataPoint(BaseModel):
    """개별 재무 데이터 포인트"""
    indicator_code: str
    period_id: int
    period_type: str
    year: int
    quarter: Optional[int] = None
    value: Optional[Union[float, int, str, bool]] = None
    unit: Optional[str] = None
    
    class Config:
        from_attributes = True


class CompanyFinancialData(BaseModel):
    """회사별 재무 데이터"""
    ticker_symbol: str
    company_name: str
    data_points: List[FinancialDataPoint]
    
    class Config:
        from_attributes = True


class FinancialDataResponse(BaseModel):
    """재무 데이터 API 응답"""
    companies: List[CompanyFinancialData]
    periods: List[FinancialPeriodOut]
    indicators: List[IndicatorDefinitionOut]


class FinancialSummaryItem(BaseModel):
    """재무 요약 항목"""
    indicator_code: str
    indicator_name: str
    latest_value: Optional[Union[float, int, str, bool]] = None
    latest_period: str
    previous_value: Optional[Union[float, int, str, bool]] = None
    previous_period: str
    change_percent: Optional[float] = None
    unit: Optional[str] = None


class CompanyFinancialSummary(BaseModel):
    """회사 재무 요약"""
    company_info: CompanyBasicInfo
    financial_summary: List[FinancialSummaryItem]


# 기본 모델
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


# 요청 스키마
class FinancialItemCreate(BaseSchema):
    item_code: str = Field(..., description="항목 코드")
    category: str = Field(..., description="항목 분류")
    standard_name: str = Field(..., description="표준화된 이름")
    description: Optional[str] = Field(None, description="항목 설명")
    display_order: Optional[int] = Field(None, description="표시 순서")


class RawMappingCreate(BaseSchema):
    mapping_id: int = Field(..., description="매핑 ID")
    raw_name: str = Field(..., description="원본 항목명")


class SummaryFinancialDataCreate(BaseSchema):
    report_id: int = Field(..., description="보고서 ID")
    company_id: int = Field(..., description="회사 ID")
    item_id: int = Field(..., description="항목 ID")
    year_month: int = Field(..., description="연월 (YYYYMM)")
    value: Decimal = Field(..., description="값 (원 단위)")
    display_unit: str = Field(..., description="표시 단위")


class ProcessFinancialReportRequest(BaseSchema):
    company_code: str = Field(..., description="회사 코드")
    report_file_path: str = Field(..., description="보고서 파일 경로")
    report_type: str = Field(..., description="보고서 유형 (annual, semi, quarter)")
    report_year: int = Field(..., description="보고서 연도")
    report_quarter: Optional[int] = Field(None, description="보고서 분기")


# 응답 스키마
class FinancialItemResponse(BaseSchema):
    id: int
    item_code: str
    category: str
    standard_name: str
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RawMappingResponse(BaseSchema):
    id: int
    mapping_id: int
    raw_name: str
    created_at: datetime
    updated_at: datetime


class FinancialItemDetailResponse(FinancialItemResponse):
    raw_mappings: List[RawMappingResponse] = []


class SummaryFinancialDataResponse(BaseSchema):
    id: int
    report_id: int
    company_id: int
    item_id: int
    year_month: int
    value: Decimal
    display_unit: str
    created_at: datetime
    updated_at: datetime


class SummaryFinancialDataDetail(BaseSchema):
    company_code: str
    company_name: str
    item_code: str
    item_name: str
    year_month: int
    value: Decimal
    display_unit: str


class FinancialDataQueryParams(BaseSchema):
    company_code: Optional[str] = None
    item_codes: Optional[List[str]] = None
    start_year_month: Optional[int] = None
    end_year_month: Optional[int] = None
    limit: int = 100
    offset: int = 0


# 요약 데이터 응답
class FinancialSummaryResponse(BaseSchema):
    company_code: str
    company_name: str
    financial_data: List[Dict[str, Any]]


# 처리 결과 응답
class ProcessResult(BaseSchema):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None 