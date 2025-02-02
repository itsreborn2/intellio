from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import uuid

class Category(Base):
    """시스템 카테고리 모델 (임시/영구 프로젝트 구분)"""
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    type = Column(String(50), nullable=False)  # 'TEMPORARY' 또는 'PERMANENT'
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), nullable=False)
