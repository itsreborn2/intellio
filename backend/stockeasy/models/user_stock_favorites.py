"""
관심기업(즐겨찾기) 모델.

사용자의 관심기업(즐겨찾기) 종목을 카테고리별로 관리합니다.
PM 지시사항에 따른 새로운 구조: 카테고리, 정렬순서, 메모 기능 포함
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from common.models.base import Base


class UserStockFavorite(Base):
    """사용자 관심기업(즐겨찾기) 모델"""
    
    __tablename__ = "user_stock_favorites"
    __table_args__ = (
        # PM 지시사항에 따른 필수 인덱스 (성능 핵심)
        Index('idx_user_category_display', 'user_id', 'category', 'display_order'),
        Index('idx_user_stock_category_unique', 'user_id', 'stock_code', 'category', unique=True),
        # 분석용 인덱스
        Index('idx_stock_code_name', 'stock_code', 'stock_name'),
        {'schema': 'stockeasy'}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(100), nullable=True)
    
    # 지시사항에 따른 새로운 필드들
    category = Column(String(50), nullable=False, default='default', comment='사용자 정의 카테고리명 (기본값: "default")')
    display_order = Column(Integer, nullable=False, default=0, comment='카테고리 내 표시 순서')
    memo = Column(Text, nullable=True, comment='사용자 메모')
    
    # created_at, updated_at은 Base 클래스에서 상속받음
    
    def __repr__(self):
        return f"<UserStockFavorite(id={self.id}, user_id={self.user_id}, stock_code={self.stock_code}, stock_name={self.stock_name}, category={self.category})>"
    
    @classmethod
    def get_default_category(cls) -> str:
        """기본 카테고리명을 반환합니다."""
        return 'default'
    
    def to_dict(self) -> dict:
        """모델을 딕셔너리로 변환합니다."""
        return {
            'id': self.id,
            'user_id': str(self.user_id),
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'category': self.category,
            'display_order': self.display_order,
            'memo': self.memo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
