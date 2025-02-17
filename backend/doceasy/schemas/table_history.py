from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class TableHistoryBase(BaseModel):
    """테이블 히스토리 기본 스키마"""
    user_id: UUID
    project_id: UUID
    document_id: UUID
    prompt: str
    title: str
    result: str

class TableHistoryCreate(TableHistoryBase):
    """테이블 히스토리 생성 스키마"""
    pass

class TableHistoryResponse(TableHistoryBase):
    """테이블 히스토리 응답 스키마"""
    id: UUID
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True

class TableHistoryList(BaseModel):
    """테이블 히스토리 목록 응답 스키마"""
    items: list[TableHistoryResponse] 