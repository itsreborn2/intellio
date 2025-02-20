from datetime import datetime
from typing import Any
from uuid import UUID as PyUUID

from sqlalchemy import DateTime, MetaData, UUID as SQLUUID, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

class UUID(TypeDecorator):
    """플랫폼 독립적인 UUID 타입"""
    impl = SQLUUID
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, PyUUID):
            return PyUUID(str(value))
        return value

class Base(DeclarativeBase):
    """기본 모델 클래스"""
    
    # Timestamp mixin
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"),
        nullable=False,
        comment="생성 시간 (Asia/Seoul)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"),
        onupdate=text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"),
        nullable=False,
        comment="수정 시간 (Asia/Seoul)"
    )

    def dict(self) -> dict[str, Any]:
        """Convert model to dictionary"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
