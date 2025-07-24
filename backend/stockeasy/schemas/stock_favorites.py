"""
관심기업(즐겨찾기) 스키마.

관심기업(즐겨찾기) API의 요청/응답 모델을 정의합니다.
PM 지시사항에 따른 카테고리, 정렬순서, 메모 기능 포함
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class StockFavoriteCreate(BaseModel):
    """관심기업(즐겨찾기) 생성 요청 모델"""
    
    stock_code: str = Field(..., description="종목 코드", max_length=10)
    stock_name: Optional[str] = Field(None, description="종목명", max_length=100)
    category: str = Field(default="default", description="카테고리명", max_length=50)
    display_order: int = Field(default=0, description="카테고리 내 표시 순서")
    memo: Optional[str] = Field(None, description="사용자 메모")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "category": "default",
                "display_order": 1,
                "memo": "주력 종목"
            }
        }


class StockFavoriteUpdate(BaseModel):
    """관심기업(즐겨찾기) 수정 요청 모델"""
    
    stock_name: Optional[str] = Field(None, description="종목명", max_length=100)
    category: Optional[str] = Field(None, description="카테고리명", max_length=50)
    display_order: Optional[int] = Field(None, description="카테고리 내 표시 순서")
    memo: Optional[str] = Field(None, description="사용자 메모")
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "AI관련",
                "display_order": 2,
                "memo": "AI 관련 주요 종목"
            }
        }


class StockFavoriteResponse(BaseModel):
    """관심기업(즐겨찾기) 응답 모델"""
    
    id: int = Field(..., description="즐겨찾기 ID")
    user_id: UUID = Field(..., description="사용자 ID")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    category: str = Field(..., description="카테고리명")
    display_order: int = Field(..., description="카테고리 내 표시 순서")
    memo: Optional[str] = Field(None, description="사용자 메모")
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
                "category": "default",
                "display_order": 1,
                "memo": "주력 종목",
                "created_at": "2025-07-24T06:00:00Z",
                "updated_at": "2025-07-24T06:00:00Z"
            }
        }


class CategoryResponse(BaseModel):
    """카테고리 응답 모델"""
    
    category: str = Field(..., description="카테고리명")
    count: int = Field(..., description="해당 카테고리의 종목 수")
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "default",
                "count": 5
            }
        }


class StockFavoritesByCategory(BaseModel):
    """카테고리별 관심기업 응답 모델"""
    
    category: str = Field(..., description="카테고리명")
    favorites: List[StockFavoriteResponse] = Field(..., description="해당 카테고리의 관심기업 목록")
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "default",
                "favorites": [
                    {
                        "id": 1,
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "stock_code": "005930",
                        "stock_name": "삼성전자",
                        "category": "default",
                        "display_order": 1,
                        "memo": "주력 종목",
                        "created_at": "2025-07-24T06:00:00Z",
                        "updated_at": "2025-07-24T06:00:00Z"
                    }
                ]
            }
        }
