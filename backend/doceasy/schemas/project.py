from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator, ConfigDict
from .document import DocumentResponse  # 문서 응답 스키마 import

class ProjectBase(BaseModel):
    """프로젝트 기본 스키마"""
    name: str = Field(..., description="프로젝트 이름")
    description: Optional[str] = Field(None, description="프로젝트 설명")
    is_temporary: bool = Field(False, description="임시 프로젝트 여부")

class ProjectCreate(ProjectBase):
    """프로젝트 생성 스키마"""
    pass

class ProjectUpdate(BaseModel):
    """프로젝트 수정 스키마"""
    name: Optional[str] = Field(None, description="프로젝트 이름")
    description: Optional[str] = Field(None, description="프로젝트 설명")
    is_temporary: Optional[bool] = Field(None, description="임시 프로젝트 여부")
    analysis_data: Optional[Dict[str, Any]] = Field(None, description="분석 데이터")

class ProjectInDB(ProjectBase):
    """데이터베이스 프로젝트 스키마"""
    id: UUID = Field(..., description="프로젝트 ID")
    created_at: datetime = Field(..., description="생성일")
    updated_at: datetime = Field(..., description="수정일")
    session_id: Optional[str] = Field(None, description="세션 ID")
    user_id: Optional[UUID] = Field(None, description="사용자 ID")

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    )

class ProjectSimpleResponse(ProjectInDB):
    """프로젝트 응답 모델"""
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    )

class ProjectListResponse(BaseModel):
    """프로젝트 목록 응답 모델"""
    total: int = Field(..., description="전체 프로젝트 수")
    items: List[ProjectSimpleResponse] = Field(default_factory=list, description="프로젝트 목록")

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    )

class RecentProjectsResponse(BaseModel):
    """최근 프로젝트 목록 응답 모델"""
    today: List[ProjectSimpleResponse] = Field(default_factory=list, description="오늘 생성된 프로젝트 목록")
    last_7_days: List[ProjectSimpleResponse] = Field(default_factory=list, description="7일 이내 생성된 프로젝트 목록")
    last_30_days: List[ProjectSimpleResponse] = Field(default_factory=list, description="30일 이내 생성된 프로젝트 목록")

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    )
