"""카테고리 관련 스키마"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class CategoryBase(BaseModel):
    """카테고리 기본 스키마"""
    name: str = Field(..., description="카테고리 이름")
    type: Optional[str] = Field(default="PERMANENT", description="카테고리 타입 (TEMPORARY/PERMANENT)")

class CategoryCreate(CategoryBase):
    """카테고리 생성 스키마"""
    type: str = Field(default="PERMANENT", description="카테고리 타입 (TEMPORARY/PERMANENT)")

class CategoryResponse(CategoryBase):
    """카테고리 응답 스키마"""
    id: UUID = Field(..., description="카테고리 ID")
    type: str = Field(..., description="카테고리 타입 (TEMPORARY/PERMANENT)")
    created_at: datetime = Field(..., description="생성일시")

    class Config:
        from_attributes = True

class AddProjectToCategory(BaseModel):
    """프로젝트를 카테고리에 추가 스키마"""
    project_id: str = Field(..., description="프로젝트 ID")

    class Config:
        from_attributes = True
