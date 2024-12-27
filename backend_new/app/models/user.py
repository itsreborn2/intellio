from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.core.config import settings

class User(Base):
    """사용자 모델"""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"


class Session(Base):
    """사용자 세션 모델"""
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_accessed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sessions", lazy="joined")
    projects = relationship("Project", back_populates="session", cascade="all, delete-orphan")

    @property
    def is_expired(self) -> bool:
        """세션 만료 여부 확인

        Returns:
            bool: 만료되었으면 True, 아니면 False
        """
        if not self.last_accessed_at:
            return True
        
        expiry_time = self.last_accessed_at + timedelta(days=settings.SESSION_EXPIRY_DAYS)
        return datetime.utcnow() > expiry_time

    @property
    def is_authenticated(self) -> bool:
        """사용자가 인증되었는지 여부"""
        return not self.is_anonymous and self.user_id is not None

    def touch(self) -> None:
        """세션 접근 시간 갱신"""
        self.last_accessed_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, session_id='{self.session_id}', user_id={self.user_id})>"
