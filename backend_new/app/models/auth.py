from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class EmailVerification(Base):
    """이메일 인증 모델"""
    __tablename__ = "email_verifications"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime]
    is_used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="email_verifications")

    @property
    def is_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<EmailVerification(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"
