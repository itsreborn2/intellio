from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.models.base import Base


class Project(Base):
    """프로젝트 모델"""
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_temporary: Mapped[bool] = mapped_column(default=True)  # True: 임시, False: 영구
    user_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # 프론트엔드용 사용자 카테고리
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    category_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("categories.id"), nullable=True)  # 카테고리 ID

    project_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_refs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 관계 설정
    user = relationship("User", back_populates="projects")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
