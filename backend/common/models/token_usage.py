from sqlalchemy import String, Integer, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from uuid import UUID
from enum import Enum
from common.models.base import Base
from common.models.user import User

class ProjectType(str, Enum):
    """프로젝트 유형"""
    DOCEASY = "doceasy"
    STOCKEASY = "stockeasy"

class TokenType(str, Enum):
    """토큰 유형"""
    LLM = "llm"
    EMBEDDING = "embedding"

class TokenUsage(Base):
    """토큰 사용량 모델"""
    __tablename__ = "token_usages"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_type: Mapped[ProjectType] = mapped_column(SQLEnum(ProjectType))
    token_type: Mapped[TokenType] = mapped_column(SQLEnum(TokenType))
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)

    # 관계 설정은 __init__.py에서 중앙화하여 처리합니다

    def __repr__(self) -> str:
        return f"<TokenUsage(id={self.id}, user_id={self.user_id}, project_type={self.project_type}, token_type={self.token_type})>" 