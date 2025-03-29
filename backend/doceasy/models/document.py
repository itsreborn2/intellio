from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, Integer, Text, ForeignKey, text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List
import json

from common.models.base import Base

# 이제 모든 관계 설정은 common/models/__init__.py에서 중앙화하여 관리합니다.

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

    # 관계 설정은 __init__.py에서 중앙화하여 처리합니다

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"

    async def process_document_chunking(self, session) -> List["DocumentChunk"]:
        """문서 텍스트를 청크로 분할하고 저장하는 메서드"""
        if not self.extracted_text:
            raise ValueError("추출된 텍스트가 없습니다.")

        # 한국어에 최적화된 텍스트 스플리터 설정
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", " ", ""]
        )

        # 텍스트 분할
        chunks = text_splitter.split_text(self.extracted_text)

        # DocumentChunk 객체 생성
        document_chunks = []
        for idx, chunk_content in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=self.id,
                chunk_index=idx,
                chunk_content=chunk_content,
                metadata=json.dumps({
                    "index": idx,
                    "document_name": self.filename,
                    "chunk_size": len(chunk_content)
                })
            )
            document_chunks.append(chunk)
            session.add(chunk)

        # 문서 상태 업데이트
        self.status = "CHUNKED"
        
        await session.flush()
        return document_chunks


class DocumentChunk(Base):
    """문서 청크 모델"""
    __tablename__ = "document_chunks"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[str | None] = mapped_column(String)  # JSON string
    embedding: Mapped[str | None] = mapped_column(String)

    # 관계 설정은 __init__.py에서 중앙화하여 처리합니다

    __table_args__ = (
        # document_id와 chunk_index의 unique 제약조건 추가
        UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunk_index'),
    ) 