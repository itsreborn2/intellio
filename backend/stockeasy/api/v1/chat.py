"""
채팅 API 라우터.

이 모듈은 채팅 세션 및 메시지 관리를 위한 API 엔드포인트를 제공합니다.
"""
import random
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Path
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from loguru import logger

from common.core.database import get_db_async
from common.models.user import Session
from common.core.deps import get_current_session
from stockeasy.services.chat_service import ChatService
from stockeasy.services.rag_service import StockRAGService
from stockeasy.api.deps import get_stock_rag_service


# API 라우터 정의
chat_router = APIRouter(prefix="/chat", tags=["채팅"])



class BaseResponse(BaseModel):
    """기본 응답 모델"""
    ok: bool
    status_message: str
# 모델 정의
class ChatSessionCreateRequest(BaseModel):
    """채팅 세션 생성 요청 모델"""
    title: str = Field(default="새 채팅", description="채팅 세션 제목")
    # stock_code: Optional[str] = Field(None, description="종목 코드")
    # stock_name: Optional[str] = Field(None, description="종목명")


class ChatSessionUpdateRequest(BaseModel):
    """채팅 세션 업데이트 요청 모델"""
    title: Optional[str] = Field(None, description="채팅 세션 제목")
    #stock_code: Optional[str] = Field(None, description="종목 코드")
    #stock_name: Optional[str] = Field(None, description="종목명")
    is_active: Optional[bool] = Field(None, description="활성화 여부")


class ChatMessageCreateRequest(BaseModel):
    """채팅 메시지 생성 요청 모델"""
    message: str = Field(..., description="메시지 내용")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")


class ChatSessionResponse(BaseResponse):
    """채팅 세션 응답 모델"""
    id: str
    user_id: str
    title: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatMessageResponse(BaseResponse):
    """채팅 메시지 응답 모델"""
    id: str
    chat_session_id: str
    role: str
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatSessionListResponse(BaseResponse):
    """채팅 세션 목록 응답 모델"""
    sessions: List[ChatSessionResponse]
    total: int


class ChatMessageListResponse(BaseResponse):
    """채팅 메시지 목록 응답 모델"""
    messages: List[ChatMessageResponse]
    total: int



# 엔드포인트 정의
@chat_router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    request: ChatSessionCreateRequest,
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> ChatSessionResponse:
    """새 채팅 세션을 생성합니다."""
    try:
        session_data = await ChatService.create_chat_session(
            db=db,
            user_id=current_session.user_id,
            title=request.title,
        )
        
        return ChatSessionResponse(**session_data)
        
    except Exception as e:
        logger.error(f"채팅 세션 생성 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 세션 생성 중 오류 발생: {str(e)}"
        )


@chat_router.get("/sessions", response_model=ChatSessionListResponse)
async def get_chat_sessions(
    is_active: Optional[bool] = Query(None, description="활성화 여부 필터"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> ChatSessionListResponse:
    """사용자의 채팅 세션 목록을 조회합니다."""
    try:
        chat_sessions = await ChatService.get_chat_sessions(
            db=db,
            user_id=current_session.user_id,
            is_active=is_active
        )
        
        return ChatSessionListResponse(
            ok=True,
            status_message="채팅 세션 목록 조회 완료",
            sessions=[ChatSessionResponse(**session) for session in chat_sessions],
            total=len(chat_sessions)
        )
        
    except Exception as e:
        logger.error(f"채팅 세션 목록 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 세션 목록 조회 중 오류 발생: {str(e)}"
        )


@chat_router.get("/sessions/{chat_session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> ChatSessionResponse:
    """특정 채팅 세션의 상세 정보를 조회합니다."""
    try:
        session_data = await ChatService.get_chat_session(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id
        )
        
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="채팅 세션을 찾을 수 없습니다."
            )
        
        return ChatSessionResponse(**session_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"채팅 세션 상세 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 세션 상세 조회 중 오류 발생: {str(e)}"
        )


@chat_router.patch("/sessions/{chat_session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    request: ChatSessionUpdateRequest = Body(...),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> ChatSessionResponse:
    """채팅 세션 정보를 업데이트합니다."""
    try:
        # 필터링된 업데이트 데이터 생성
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        
        session_data = await ChatService.update_chat_session(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id,
            update_data=update_data
        )
        
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="채팅 세션을 찾을 수 없습니다."
            )
        
        return ChatSessionResponse(**session_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"채팅 세션 업데이트 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 세션 업데이트 중 오류 발생: {str(e)}"
        )


@chat_router.delete("/sessions/{chat_session_id}", response_model=BaseResponse)
async def delete_chat_session(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> BaseResponse:
    """채팅 세션을 삭제합니다."""
    try:
        success = await ChatService.delete_chat_session(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="채팅 세션을 찾을 수 없습니다."
            )
        
        return BaseResponse(
            ok=True,
            status_message="채팅 세션이 성공적으로 삭제되었습니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"채팅 세션 삭제 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 세션 삭제 중 오류 발생: {str(e)}"
        )


@chat_router.post("/sessions/{chat_session_id}/messages", response_model=ChatMessageResponse)
async def create_chat_message(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    request: ChatMessageCreateRequest = Body(...),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session),
    stock_rag_service: StockRAGService = Depends(get_stock_rag_service)
) -> ChatMessageResponse:
    """새 채팅 메시지를 생성하고 응답을 생성합니다."""
    try:
        logger.info(f"create_chat_message 호출: {request}")
        # 세션 존재 여부 확인
        session_data = await ChatService.get_chat_session(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id
        )
        
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="채팅 세션을 찾을 수 없습니다."
            )
        
        logger.info(f"session_data: {session_data}")
        # 사용자 메시지 저장
        user_message = await ChatService.create_chat_message(
            db=db,
            session_id=chat_session_id,
            role="user",
            content=request.message,
            stock_code=request.stock_code,
            stock_name=request.stock_name
        )
        logger.info(f"user_message: {user_message}")
        
        # LLM으로 응답 생성
        # StockRAGService를 사용하여 응답 생성
        # rag_result = await stock_rag_service.analyze_stock(
        #     query=request.message,
        #     stock_code=request.stock_code,
        #     stock_name=request.stock_name,
        #     session_id=str(current_session.id),
        #     user_id=str(current_session.user_id)
        # )

        # 응답 정보 추출
        # answer = rag_result.get('answer', '')
        # answer_expert = rag_result.get('answer_expert', '')

        # # 메타데이터 설정
        # metadata = {
        #     "rag_result": {
        #         "trace_id": rag_result.get("trace_id"),
        #         # 필요한 경우 추가 메타데이터 설정
        #     }
        # }
        # 랜덤 숫자.
        answer = f"어시스턴트 응답 저장 : {random.randint(1, 1000000)}"
        metadata = ""
        logger.info(f"어시스턴트 응답 저장 : {answer}")
        # 어시스턴트 응답 저장
        # 실제 ChatService 호출 대신 더미 데이터 사용
        assistant_message = {
            "id": str(uuid4()),
            "chat_session_id": str(chat_session_id),
            "role": "assistant",
            "content": answer,
            "stock_code": request.stock_code,
            "stock_name": request.stock_name,
            "metadata": metadata,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        #실제 응답 저장은 비동기적으로 처리 (필요한 경우)
        assistant_message = await ChatService.create_chat_message(
            db=db,
            session_id=chat_session_id,
            role="assistant",
            content=answer,
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            metadata=metadata
        )
        assistant_message["ok"] = True
        assistant_message["status_message"] = "정상 응답 완료"
        logger.info(f"어시스턴트 응답 완료")
        return ChatMessageResponse(**assistant_message)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("채팅 메시지 생성 중 오류 발생: {}", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 메시지 생성 중 오류 발생: {str(e)}"
        )


@chat_router.get("/sessions/{chat_session_id}/messages", response_model=ChatMessageListResponse)
async def get_chat_messages(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    limit: int = Query(100, ge=1, le=500, description="조회할 최대 메시지 수"),
    offset: int = Query(0, ge=0, description="조회 시작 위치"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> ChatMessageListResponse:
    """특정 채팅 세션의 메시지 목록을 조회합니다."""
    try:
        # DB이 실제 세션이 있는지 확인.
        session_data = await ChatService.get_chat_session(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id
        )
        
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="채팅 세션을 찾을 수 없습니다."
            )
        
        # 메시지 목록 조회
        messages = await ChatService.get_chat_messages(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id,
            limit=limit,
            offset=offset
        )
        
        logger.debug(f"{session_data['title']} :총  {len(messages)} 메세지")
        
        return ChatMessageListResponse(
            messages=[ChatMessageResponse(**message) for message in messages],
            total=len(messages),
            ok=True,
            status_message="채팅 메시지 목록 조회 완료"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"채팅 메시지 목록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 메시지 목록 조회 중 오류 발생: {str(e)}"
        ) 