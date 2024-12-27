from uuid import UUID
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict, field_validator, validator
from datetime import datetime
import json

from app.schemas.base import BaseSchema, TimestampSchema, ResponseSchema

# 문서 상태 타입 정의
DocumentStatusType = Literal[
    'REGISTERED',
    'UPLOADING',
    'UPLOADED',
    'PROCESSING',
    'COMPLETED',
    'PARTIAL',
    'ERROR',
    'DELETED'
]

class DocumentBase(BaseSchema):
    """문서 기본 스키마"""
    filename: str = Field(..., min_length=1, max_length=255, description="문서 파일명")
    mime_type: str = Field(..., max_length=100, description="MIME 타입")
    file_size: int = Field(..., gt=0, description="파일 크기 (bytes)")

class DocumentCreate(DocumentBase):
    """문서 생성 스키마"""
    project_id: UUID = Field(..., description="프로젝트 ID")
    file_path: str = Field(..., max_length=1000, description="파일 경로")

class DocumentUpdate(BaseSchema):
    """문서 업데이트 스키마"""
    status: Optional[DocumentStatusType] = Field(None, description="문서 상태")
    error_message: Optional[str] = Field(None, max_length=1000, description="에러 메시지")

class DocumentInDB(DocumentBase, TimestampSchema):
    """데이터베이스의 문서 스키마"""
    id: UUID = Field(..., description="문서 ID")
    project_id: UUID = Field(..., description="프로젝트 ID")
    file_path: str = Field(..., description="파일 경로")
    status: DocumentStatusType = Field(..., description="문서 상태")
    error_message: Optional[str] = Field(None, description="에러 메시지")

class DocumentResponse(DocumentBase, TimestampSchema):
    """문서 응답 스키마"""
    id: UUID = Field(..., description="문서 ID")
    project_id: UUID = Field(..., description="프로젝트 ID")
    file_path: str = Field(..., description="파일 경로")
    status: DocumentStatusType = Field(..., description="문서 상태")
    error_message: Optional[str] = Field(None, description="에러 메시지")
    chunk_count: int = Field(0, description="청크 수")
    download_url: Optional[HttpUrl] = Field(None, description="다운로드 URL")
    embedding_ids: Optional[List[str]] = Field(None, description="임베딩 ID 목록")
    extracted_text: Optional[str] = Field(None, description="추출된 텍스트")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    @validator('embedding_ids', pre=True)
    def parse_embedding_ids(cls, v):
        """Parse embedding_ids from JSON string to list"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v

class DocumentListResponse(BaseSchema):
    """문서 목록 응답 스키마"""
    total: int = Field(..., description="문서 총 개수")
    items: List[DocumentResponse] = Field(..., description="문서 목록")

class DocumentChunkBase(BaseSchema):
    """문서 청크 기본 스키마"""
    content: str = Field(..., description="청크 내용")
    metadata: Optional[str] = Field(None, description="청크 메타데이터")

class DocumentChunkCreate(DocumentChunkBase):
    """문서 청크 생성 스키마"""
    document_id: UUID = Field(..., description="문서 ID")

class DocumentChunkInDB(DocumentChunkBase, TimestampSchema):
    """데이터베이스의 문서 청크 스키마"""
    id: UUID = Field(..., description="청크 ID")
    document_id: UUID = Field(..., description="문서 ID")
    embedding: Optional[str] = Field(None, description="임베딩 데이터")

class DocumentChunkResponse(DocumentChunkInDB):
    """문서 청크 응답 스키마"""
    pass

class DocumentUploadResponse(BaseSchema):
    """문서 업로드 응답"""
    success: bool = Field(True, description="업로드 성공 여부")
    project_id: UUID = Field(..., description="프로젝트 ID")
    document_ids: List[UUID] = Field(..., description="문서 ID 목록")

class DocumentQueryRequest(BaseSchema):
    """문서 쿼리 요청 스키마"""
    query: str = Field(..., min_length=1, description="쿼리 문자열")
    context: Optional[str] = Field(None, description="컨텍스트")
    mode: str = Field("chat", description="모드", pattern="^(chat|table)$")
