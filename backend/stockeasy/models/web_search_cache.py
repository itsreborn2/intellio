from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey, Text, DateTime, Column, Index, text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from common.models.base import Base
from pgvector.sqlalchemy import Vector

# --- Embedding 차원 수 설정 ---
# OpenAI text-embedding-3-large 기본 차원 수
EMBEDDING_DIM = 3072

class WebSearchQueryCache(Base):
    """웹 검색 쿼리 캐시 테이블"""
    __tablename__ = "web_search_query_cache"
    __table_args__ = {"schema": "stockeasy"}
    
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    stock_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    stock_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"),
        onupdate=text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"),
        nullable=False,
        comment="수정 시간 (Asia/Seoul)"
    )
    
    results: Mapped[List["WebSearchResultCache"]] = relationship(
        "WebSearchResultCache", 
        back_populates="query_cache",
        cascade="all, delete-orphan"
    )

class WebSearchResultCache(Base):
    """웹 검색 결과 캐시 테이블"""
    __tablename__ = "web_search_result_cache"
    __table_args__ = {"schema": "stockeasy"}
    
    id: Mapped[int] = mapped_column(primary_key=True)
    query_cache_id: Mapped[int] = mapped_column(ForeignKey("stockeasy.web_search_query_cache.id", ondelete="CASCADE"))
    title: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    search_query: Mapped[Optional[str]] = mapped_column(Text)
    search_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    query_cache: Mapped["WebSearchQueryCache"] = relationship("WebSearchQueryCache", back_populates="results") 