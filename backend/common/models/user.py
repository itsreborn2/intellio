from sqlalchemy import String, Boolean, ForeignKey, func, event, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from datetime import datetime, timedelta, timezone
from uuid import  UUID
from typing import Optional, List
from common.models.base import Base
from common.core.config import settings
import logging

# TokenUsage 모델에 대한 순환 참조 문제를 방지하기 위해 직접 임포트하지 않음
# 대신 클래스 초기화 완료 후 SQLAlchemy가 관계를 해석할 수 있도록 문자열 참조 사용

# 순환 참조를 해결하기 위한 필요한 클래스 임포트
from doceasy.models.project import Project  # Project 모델 명시적 임포트 추가

# 이제 모든 관계 설정은 common/models/__init__.py에서 중앙화하여 관리합니다.

class User(Base):
    """사용자 모델"""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # OAuth 사용자는 비밀번호가 없을 수 있음
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # google, naver, kakao
    oauth_provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 프로필 이미지 URL

    # 관계 설정은 __init__.py에서 중앙화하여 처리합니다

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"

# 모든 모델 정의 후 명시적으로 관계 로드를 위한 코드
try:
    # 모듈 로딩 시점에서 TokenUsage 로드 시도
    from common.models.token_usage import TokenUsage
    logging.info("TokenUsage 모델 로드 성공")
except ImportError:
    logging.warning("TokenUsage 모델 로드 실패 - 순환 참조 가능성 있음")
    pass  # 무시하고 계속 진행

class Session(Base):
    """사용자 세션 모델"""
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email", ondelete="CASCADE"), nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(default=True)
    last_accessed_at: Mapped[datetime] = mapped_column(
                                                    DateTime(timezone=True),
                                                    server_default=text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"),
                                                    nullable=False
                                                )
    # 관계 설정은 __init__.py에서 중앙화하여 처리합니다

    @property
    def is_expired(self) -> bool:
        """세션 만료 여부 확인

        Returns:
            bool: 만료되었으면 True, 아니면 False
        """
        if not self.last_accessed_at:
            return True
        
        # timezone-aware한 현재 시간 생성
        current_time = datetime.now(timezone.utc)
        expiry_time = self.last_accessed_at + timedelta(days=settings.SESSION_EXPIRY_DAYS)
        return current_time > expiry_time

    @property
    def is_authenticated(self) -> bool:
        """사용자가 인증되었는지 여부"""
        return not self.is_anonymous and self.user_id is not None

    def touch(self) -> None:
        """세션 접근 시간 갱신"""
        self.last_accessed_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id})>"
