from typing import Optional, List
from uuid import uuid4
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, text, Boolean, Index, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from common.models.base import Base
from uuid import UUID as PyUUID

class StockChatSession(Base):
    """주식 채팅 세션 테이블
    
    사용자와 주식 종목 간의 대화 세션을 나타냅니다.
    """
    __tablename__ = "stockeasy_chat_sessions"
    __table_args__ = (
        {"schema": "stockeasy"}  # stockeasy 스키마 사용
    )
    
    id: Mapped[PyUUID] = mapped_column(
        UUID, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
        comment="채팅 세션 ID"
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, index=True,
        comment="사용자 ID"
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, 
        server_default="새 채팅",
        comment="채팅 세션 제목"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, 
        server_default=text("true"),
        comment="활성화 여부"
    )
    # 종목 정보 필드 추가
    stock_code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, index=True,
        comment="종목 코드"
    )
    stock_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="종목명"
    )
    # 추가 종목 정보를 JSON으로 저장
    stock_info: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="종목 관련 추가 정보 (업종, 시가총액 등)"
    )
    # 에이전트 처리 결과 데이터
    agent_results: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="세션의 에이전트 처리 결과 데이터"
    )
    # 역참조 관계 (ChatMessage 모델에서 정의)
    messages: Mapped[List["StockChatMessage"]] = relationship(
        "StockChatMessage", 
        back_populates="session", 
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # 사용자 테이블과의 관계
    user = relationship("User", back_populates="stock_chat_sessions", lazy="joined")
    
    @property
    def to_dict(self) -> dict:
        """세션 객체를 딕셔너리로 변환"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "is_active": self.is_active,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "stock_info": self.stock_info,
            "agent_results": self.agent_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class StockChatMessage(Base):
    """주식 채팅 메시지 테이블
    
    채팅 세션 내의 개별 메시지를 나타냅니다.
    다양한 유형의 콘텐츠(텍스트, 이미지, 차트 등)를 지원합니다.
    """
    __tablename__ = "stockeasy_chat_messages"
    __table_args__ = (
        # 인덱스 추가 - 세션별 메시지 조회 성능 향상
        Index("ix_stockeasy_chat_messages_chat_session_id_created_at", 
              "chat_session_id", "created_at"),
        {"schema": "stockeasy"}  # stockeasy 스키마 사용
    )
    
    id: Mapped[PyUUID] = mapped_column(
        UUID, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
        comment="메시지 ID"
    )
    chat_session_id: Mapped[PyUUID] = mapped_column(
        UUID, ForeignKey("stockeasy.stockeasy_chat_sessions.id", ondelete="CASCADE"), 
        nullable=False, index=True,
        comment="채팅 세션 ID"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="메시지 역할 (user, assistant, system)"
    )
    
    # 종목 코드와 종목명 추가
    stock_code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="종목 코드"
    )
    stock_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="종목명"
    )
    
    # 콘텐츠 타입 필드 추가
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, 
        server_default="text",
        comment="메시지 콘텐츠 타입 (text, image, chart, file, card 등)"
    )
    
    # 텍스트 콘텐츠 (assistant 메시지가 components를 사용하는 경우 nullable)
    content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="메시지 텍스트 내용"
    )

    content_expert: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="전문가 메시지 텍스트 내용"
    )
    
    # 구조화된 메시지 컴포넌트 (새로 추가)
    components: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB, nullable=True,
        comment="구조화된 메시지 컴포넌트 배열 (제목, 단락, 차트, 테이블 등)"
    )
    
    # 구조화된 메시지 데이터
    message_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="메시지 타입별 구조화된 데이터 (차트 데이터, 카드 정보 등)"
    )
    
    # 외부 리소스 URL
    data_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="외부 리소스 URL (이미지, 차트 데이터 등)"
    )
    
    # 메타데이터 (추가 정보, 처리 관련 정보 등)
    message_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="메시지 추가 메타데이터 (처리 정보, 컨텍스트 등)"
    )
    
    # 에이전트 처리 결과 데이터
    agent_results: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="에이전트 처리 결과 데이터"
    )
    
    # 세션과의 관계
    session: Mapped["StockChatSession"] = relationship(
        "StockChatSession", 
        back_populates="messages",
        foreign_keys=[chat_session_id],
        lazy="joined"
    )
    
    @property
    def to_dict(self) -> dict:
        """메시지 객체를 딕셔너리로 변환"""
        return {
            "id": str(self.id),
            "chat_session_id": str(self.chat_session_id),
            "role": self.role,
            "content_type": self.content_type,
            "content": self.content,
            "content_expert": self.content_expert,
            "components": self.components,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "message_data": self.message_data,
            "data_url": self.data_url,
            "message_metadata": self.message_metadata,
            "agent_results": self.agent_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ShareStockChatSession(Base):
    """공유된 주식 채팅 세션 테이블
    
    공유를 위해 복제된 채팅 세션을 나타냅니다.
    """
    __tablename__ = "stockeasy_shared_chat_sessions"
    __table_args__ = (
        {"schema": "stockeasy"}
    )
    
    id: Mapped[PyUUID] = mapped_column(
        UUID, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
        comment="공유 세션 ID"
    )
    original_session_id: Mapped[PyUUID] = mapped_column(
        UUID, ForeignKey("stockeasy.stockeasy_chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="원본 채팅 세션 ID"
    )

    # 공유 링크만 만료시키거나 재생성하면서 원본 데이터는 유지 가능
    share_uuid: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True,
        comment="공유 링크용 UUID"
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="채팅 세션 제목"
    )
    # 로딩 횟수 필드 추가
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
        comment="세션 조회 횟수"
    )
    # 종목 정보 필드
    stock_code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, index=True,
        comment="종목 코드"
    )
    stock_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="종목명"
    )
    # 추가 종목 정보를 JSON으로 저장
    stock_info: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="종목 관련 추가 정보"
    )
    # 에이전트 처리 결과 데이터
    agent_results: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="세션의 에이전트 처리 결과 데이터"
    )
    # 역참조 관계
    messages: Mapped[List["ShareStockChatMessage"]] = relationship(
        "ShareStockChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    @property
    def to_dict(self) -> dict:
        """세션 객체를 딕셔너리로 변환"""
        return {
            "id": str(self.id),
            "original_session_id": str(self.original_session_id),
            "share_uuid": self.share_uuid,
            "title": self.title,
            "view_count": self.view_count,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "stock_info": self.stock_info,
            "agent_results": self.agent_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ShareStockChatMessage(Base):
    """공유된 주식 채팅 메시지 테이블
    
    공유된 채팅 세션 내의 개별 메시지를 나타냅니다.
    """
    __tablename__ = "stockeasy_shared_chat_messages"
    __table_args__ = (
        Index("ix_stockeasy_shared_chat_messages_chat_session_id_created_at", 
              "chat_session_id", "created_at"),
        {"schema": "stockeasy"}
    )
    
    id: Mapped[PyUUID] = mapped_column(
        UUID, primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
        comment="공유 메시지 ID"
    )
    chat_session_id: Mapped[PyUUID] = mapped_column(
        UUID, ForeignKey("stockeasy.stockeasy_shared_chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="공유 채팅 세션 ID"
    )
    original_message_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID, nullable=True,
        comment="원본 메시지 ID"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="메시지 역할 (user, assistant, system)"
    )
    # 기존 StockChatMessage와 동일한 필드들 추가
    stock_code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="종목 코드"
    )
    stock_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="종목명"
    )
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        server_default="text",
        comment="메시지 콘텐츠 타입"
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="메시지 텍스트 내용"
    )
    content_expert: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="전문가 메시지 텍스트 내용"
    )
    components: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB, nullable=True,
        comment="구조화된 메시지 컴포넌트 배열"
    )
    message_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="메시지 타입별 구조화된 데이터"
    )
    data_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="외부 리소스 URL"
    )
    message_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="메시지 추가 메타데이터"
    )
    agent_results: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="에이전트 처리 결과 데이터"
    )
    # 세션과의 관계
    session: Mapped["ShareStockChatSession"] = relationship(
        "ShareStockChatSession",
        back_populates="messages",
        foreign_keys=[chat_session_id],
        lazy="joined"
    )
    
    @property
    def to_dict(self) -> dict:
        """메시지 객체를 딕셔너리로 변환"""
        return {
            "id": str(self.id),
            "chat_session_id": str(self.chat_session_id),
            "original_message_id": str(self.original_message_id) if self.original_message_id else None,
            "role": self.role,
            "content_type": self.content_type,
            "content": self.content,
            "content_expert": self.content_expert,
            "components": self.components,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "message_data": self.message_data,
            "data_url": self.data_url,
            "message_metadata": self.message_metadata,
            "agent_results": self.agent_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        } 