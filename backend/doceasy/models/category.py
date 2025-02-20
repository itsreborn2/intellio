from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from common.models.base import Base


class Category(Base):
    """시스템 카테고리 모델 (임시/영구 프로젝트 구분)"""
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    type: Mapped[str] = mapped_column(String(50))  # 'TEMPORARY' 또는 'PERMANENT'

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
