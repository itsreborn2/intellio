from datetime import datetime
from uuid import UUID
from typing import Optional

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.base import Base

class OAuth2Account(Base):
    """OAuth2 계정 모델"""
    __tablename__ = "oauth2_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))  # google, github 등
    account_id: Mapped[str] = mapped_column(String(100))  # provider의 고유 ID
    email: Mapped[str] = mapped_column(String(255))
    access_token: Mapped[str] = mapped_column(String(2000))  # OAuth 토큰은 길 수 있음
    expires_at: Mapped[datetime] = mapped_column()
    refresh_token: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    # Relationships
    user = relationship("User", back_populates="oauth_accounts", lazy="joined")

    def __repr__(self) -> str:
        return f"<OAuth2Account(id={self.id}, provider='{self.provider}', email='{self.email}')>"
