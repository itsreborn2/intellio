"""
이 모듈은 모든 모델 클래스를 임포트하고 관계를 설정합니다.
순환 참조 문제를 해결하기 위해 모든 모델 관계를 중앙에서 관리합니다.
"""

# SQLAlchemy 관계 함수 임포트
from sqlalchemy.orm import relationship

# 모든 모델 클래스를 임포트합니다
from common.models.base import Base
from common.models.user import User, Session
from common.models.token_usage import TokenUsage, ProjectType, TokenType

# doceasy 모델
from doceasy.models.project import Project
from doceasy.models.document import Document, DocumentChunk
from doceasy.models.category import Category
from doceasy.models.chat import ChatHistory
from doceasy.models.table_history import TableHistory

# stockeasy 모델
from stockeasy.models.telegram_message import TelegramMessage
#from stockeasy.models.agent_io import AgentSession, AgentMessage

# 관계 설정을 중앙화합니다
# User 관계
User.token_usages = relationship("TokenUsage", back_populates="user", cascade="all, delete-orphan")
User.projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
User.sessions = relationship("Session", back_populates="user", foreign_keys="[Session.user_id]", cascade="all, delete-orphan")

# Session 관계
Session.user = relationship("User", back_populates="sessions", foreign_keys=[Session.user_id], lazy="joined")

# TokenUsage 관계
TokenUsage.user = relationship("User", back_populates="token_usages")

# Project 관계
Project.user = relationship("User", back_populates="projects")
Project.documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")

# Document 관계
Document.project = relationship("Project", back_populates="documents")
Document.chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

# DocumentChunk 관계
DocumentChunk.document = relationship("Document", back_populates="chunks")

__all__ = [
    "Base",
    "User",
    "Session",
    "TokenUsage",
    "ProjectType",
    "TokenType",
    "Project",
    "Document",
    "DocumentChunk",
    "Category",
    "ChatHistory",
    "TableHistory",
    "TelegramMessage",
    "AgentSession",
    "AgentMessage"
] 