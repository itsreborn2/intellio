"""
RS(상대강도) 데이터 스키마 정의

이 모듈은 구글 시트에서 가져온 RS 데이터를 처리하기 위한 Pydantic 스키마를 정의합니다.
구글 시트 헤더: 종목코드, 종목명, 업종, RS, RS_1M, RS_2M, RS_3M, RS_6M, MMT
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class RSData(BaseModel):
    """RS(상대강도) 개별 종목 데이터"""
    stock_code: str = Field(..., description="종목코드")
    stock_name: str = Field(..., description="종목명")
    sector: Optional[str] = Field(None, description="업종")
    rs: Optional[float] = Field(None, description="RS 값")
    rs_1m: Optional[float] = Field(None, description="1개월 RS 값")
    rs_2m: Optional[float] = Field(None, description="2개월 RS 값")
    rs_3m: Optional[float] = Field(None, description="3개월 RS 값")
    rs_6m: Optional[float] = Field(None, description="6개월 RS 값")
    mmt: Optional[float] = Field(None, description="MMT 값")
    
    class Config:
        """Pydantic 설정"""
        json_encoders = {
            float: lambda v: round(v, 4) if v is not None else None
        }


class RSDataResponse(BaseModel):
    """RS 데이터 응답 스키마"""
    count: int = Field(..., description="조회된 데이터 개수")
    last_updated: Optional[datetime] = Field(None, description="마지막 업데이트 시간")
    data: List[RSData] = Field(..., description="RS 데이터 리스트")
    status: str = Field(default="success", description="응답 상태")


class CompressedRSDataResponse(BaseModel):
    """압축된 RS 데이터 응답 스키마 (대량 데이터용)"""
    count: int = Field(..., description="조회된 데이터 개수")
    last_updated: Optional[datetime] = Field(None, description="마지막 업데이트 시간")
    compressed: bool = Field(default=True, description="압축 여부")
    headers: List[str] = Field(..., description="데이터 헤더")
    data: List[List[Any]] = Field(..., description="압축된 데이터 배열")
    status: str = Field(default="success", description="응답 상태")


class SingleRSDataResponse(BaseModel):
    """개별 종목 RS 데이터 응답 스키마"""
    stock_code: str = Field(..., description="조회된 종목코드")
    data: Optional[RSData] = Field(None, description="RS 데이터")
    status: str = Field(default="success", description="응답 상태")
    message: Optional[str] = Field(None, description="메시지")


class RSUpdateRequest(BaseModel):
    """RS 데이터 업데이트 요청 스키마"""
    force_update: bool = Field(default=False, description="강제 업데이트 여부")


class RSUpdateResponse(BaseModel):
    """RS 데이터 업데이트 응답 스키마"""
    message: str = Field(..., description="응답 메시지")
    updated_count: int = Field(..., description="업데이트된 데이터 개수")
    last_updated: datetime = Field(..., description="업데이트 시간")
    status: str = Field(default="success", description="응답 상태") 