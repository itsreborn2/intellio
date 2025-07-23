"""
RS 즐겨찾기 스키마.

RS 즐겨찾기 API의 요청/응답 모델을 정의합니다.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RSFavoriteCreate(BaseModel):
    """RS 즐겨찾기 생성 요청 모델"""
    
    stock_code: str = Field(..., description="종목 코드", max_length=10)
    stock_name: Optional[str] = Field(None, description="종목명", max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "005930",
                "stock_name": "삼성전자"
            }
        }


class RSFavoriteResponse(BaseModel):
    """RS 즐겨찾기 응답 모델"""
    
    id: int = Field(..., description="즐겨찾기 ID")
    user_id: UUID = Field(..., description="사용자 ID")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime = Field(..., description="수정 시간")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "created_at": "2025-07-23T06:00:00Z",
                "updated_at": "2025-07-23T06:00:00Z"
            }
        }


class RSFavoriteToggleRequest(BaseModel):
    """RS 즐겨찾기 토글 요청 모델"""
    
    stock_code: str = Field(..., description="종목 코드", max_length=10)
    stock_name: Optional[str] = Field(None, description="종목명", max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "005930",
                "stock_name": "삼성전자"
            }
        }


class RSFavoriteToggleResponse(BaseModel):
    """RS 즐겨찾기 토글 응답 모델"""
    
    is_favorite: bool = Field(..., description="즐겨찾기 여부")
    message: str = Field(..., description="응답 메시지")
    favorite: Optional[RSFavoriteResponse] = Field(None, description="즐겨찾기 정보 (추가된 경우)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_favorite": True,
                "message": "즐겨찾기에 추가되었습니다.",
                "favorite": {
                    "id": 1,
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "created_at": "2025-07-23T06:00:00Z",
                    "updated_at": "2025-07-23T06:00:00Z"
                }
            }
        }
