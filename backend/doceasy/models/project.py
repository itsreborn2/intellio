from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from common.models.base import Base
import uuid

class Project(Base):
    """프로젝트 모델"""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_temporary = Column(Boolean, default=True)  # True: 임시, False: 영구
    user_category = Column(String(255), nullable=True)  # 프론트엔드용 사용자 카테고리
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    #session_id = Column(String(255), ForeignKey("sessions.session_id"), nullable=True) # 프로젝트와 세션은 관계가 없음. 일단 제거.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)  # 카테고리 ID 추가

    project_metadata = Column(Text, nullable=True)
    content_data = Column(Text, nullable=True)
    embedding_refs = Column(Text, nullable=True)

    # 관계 설정
    user = relationship("User", back_populates="projects")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
