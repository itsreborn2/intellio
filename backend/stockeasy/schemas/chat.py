from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ShareLinkResponse(BaseModel):
    """공유 링크 생성 응답 스키마"""
    share_uuid: str = Field(..., description="공유 링크용 UUID")
    share_url: str = Field(..., description="공유 페이지 접근 URL")


class SharedChatSessionResponse(BaseModel):
    """공유된 채팅 세션 응답 스키마"""
    id: str = Field(..., description="공유 세션 ID")
    share_uuid: str = Field(..., description="공유 링크용 UUID")
    title: str = Field(..., description="채팅 세션 제목")
    stock_code: Optional[str] = Field(None, description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    stock_info: Optional[Dict[str, Any]] = Field(None, description="종목 관련 추가 정보")
    created_at: Optional[datetime] = Field(None, description="세션 생성 시간")
    updated_at: Optional[datetime] = Field(None, description="세션 마지막 수정 시간")


class SharedChatMessageResponse(BaseModel):
    """공유된 채팅 메시지 응답 스키마"""
    id: str = Field(..., description="메시지 ID")
    chat_session_id: str = Field(..., description="채팅 세션 ID")
    original_message_id: Optional[str] = Field(None, description="원본 메시지 ID")
    role: str = Field(..., description="메시지 역할 (user, assistant, system)")
    content_type: str = Field(..., description="메시지 콘텐츠 타입")
    content: Optional[str] = Field(None, description="메시지 텍스트 내용")
    content_expert: Optional[str] = Field(None, description="전문가 메시지 텍스트 내용")
    components: Optional[List[Dict[str, Any]]] = Field(None, description="구조화된 메시지 컴포넌트 배열")
    stock_code: Optional[str] = Field(None, description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    message_data: Optional[Dict[str, Any]] = Field(None, description="메시지 타입별 구조화된 데이터")
    data_url: Optional[str] = Field(None, description="외부 리소스 URL")
    message_metadata: Optional[Dict[str, Any]] = Field(None, description="메시지 추가 메타데이터")
    agent_results: Optional[Dict[str, Any]] = Field(None, description="에이전트 처리 결과 데이터")
    created_at: Optional[datetime] = Field(None, description="메시지 생성 시간")
    updated_at: Optional[datetime] = Field(None, description="메시지 마지막 수정 시간")


class SharedChatResponse(BaseModel):
    """공유된 채팅 전체 응답 스키마"""
    session: SharedChatSessionResponse
    messages: List[SharedChatMessageResponse] 