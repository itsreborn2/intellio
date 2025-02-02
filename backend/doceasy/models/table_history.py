from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, ForeignKey, DateTime, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

class TableHistory(Base):
    """테이블 모드 히스토리 모델"""
    __tablename__ = "table_histories"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    prompt: Mapped[str] = mapped_column(String, nullable=False)  # 사용자 입력값
    title: Mapped[str] = mapped_column(String, nullable=False)   # 축약된 제목
    result: Mapped[str] = mapped_column(String, nullable=False)  # 문서 검색 결과
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint('project_id', 'document_id', 'prompt', name='uix_project_document_prompt'),
    ) 