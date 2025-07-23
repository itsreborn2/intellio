"""
RS 즐겨찾기 모델.

사용자의 RS 페이지 즐겨찾기 종목을 관리합니다.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from common.models.base import Base


class UserRSFavorite(Base):
    """사용자 RS 즐겨찾기 모델"""
    
    __tablename__ = "user_rs_favorites"
    __table_args__ = (
        Index('ix_user_rs_favorites_user_stock_unique', 'user_id', 'stock_code', unique=True),
        {'schema': 'stockeasy'}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<UserRSFavorite(id={self.id}, user_id={self.user_id}, stock_code={self.stock_code}, stock_name={self.stock_name})>"
