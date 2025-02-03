from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.base import Base


class Document(Base):
    """문서 모델"""
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))  # 원본 파일명
    file_path: Mapped[str] = mapped_column(String(1000))  # 스토리지 내 파일 경로
    file_type: Mapped[str] = mapped_column(String(100))  # 파일 타입 (예: txt, pdf, docx)
    mime_type: Mapped[str | None] = mapped_column(String(100))  # MIME 타입 (예: text/plain)
    file_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='REGISTERED')  # 문서 상태
    error_message: Mapped[str | None] = mapped_column(String(1000))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    embedding_ids: Mapped[str | None] = mapped_column(String)  # JSON string of list
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class DocumentChunk(Base):
    """문서 청크 모델"""
    __tablename__ = "document_chunks"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str | None] = mapped_column(String)
    chunk_metadata: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")
