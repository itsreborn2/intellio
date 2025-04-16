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
from sse_starlette.sse import EventSourceResponse
import json
import asyncio
import time

from common.services.agent_llm import refresh_agent_llm_cache
from stockeasy.services.financial.stock_info_service import StockInfoService
from common.core.database import get_db_async
from common.models.user import Session
from common.core.deps import get_current_session
from stockeasy.services.chat_service import ChatService
from stockeasy.services.rag_service import StockRAGService
from stockeasy.api.deps import get_stock_rag_service
from common.core.memory import chat_memory_manager


# 챗 라우터 정의 위에 도우미 함수 추가
def get_user_friendly_agent_message(agent: str, status: str) -> str:
    """
    에이전트 이름과 상태(시작/완료)에 따라 사용자 친화적인 메시지를 반환합니다.
    
    Args:
        agent: 에이전트 이름
        status: 'start' 또는 'complete'
        
    Returns:
        사용자 친화적인 메시지
    """
    agent_messages = {
        "session_manager": {
            "start": "세션 초기화 중...",
            "complete": "세션 초기화 완료"
        },
        "orchestrator": {
            "start": "질문 분석 전략 수립 중...",
            "complete": "분석 계획 수립 완료"
        },
        "question_analyzer": {
            "start": "질문 의도 파악 중...",
            "complete": "질문 분석 완료"
        },
        "telegram_retriever": {
            "start": "내부 데이터 정보 검색 중...",
            "complete": "내부 데이터 검색 완료"
        },
        "report_analyzer": {
            "start": "기업 보고서 분석 중...",
            "complete": "기업 보고서 분석 완료"
        },
        "financial_analyzer": {
            "start": "재무 데이터 분석 중...",
            "complete": "재무 분석 완료"
        },
        "revenue_breakdown": {
            "start": "매출 및 수주 현황 분석 중...",
            "complete": "매출 및 수주 현황 분석 완료"
        },
        "industry_analyzer": {
            "start": "산업 및 경쟁사 분석 중...",
            "complete": "산업 분석 완료"
        },
        "confidential_analyzer": {
            "start": "비공개 정보 분석 중...",
            "complete": "비공개 정보 분석 완료"
        },
        "knowledge_integrator": {
            "start": "수집된 정보 통합 중...",
            "complete": "정보 통합 완료"
        },
        "summarizer": {
            "start": "결과 요약 생성 중...",
            "complete": "요약 생성 완료"
        },
        "response_formatter": {
            "start": "답변 형식 최적화 중...",
            "complete": "답변 형식화 완료"
        },
        "fallback_manager": {
            "start": "대체 정보 탐색 중...",
            "complete": "대체 정보 탐색 완료"
        },
        "parallel_search": {
            "start": "다중 데이터 소스 검색 시작...",
            "complete": "데이터 검색 완료"
        },
        "context_response": {
            "start": "이전 대화 맥락 고려 중...",
            "complete": "대화 맥락 분석 완료"
        }
    }
    
    # 기본 메시지 (에이전트가 맵핑에 없는 경우)
    default_messages = {
        "start": f"{agent} 에이전트가 데이터 분석을 시작합니다.",
        "complete": f"{agent} 에이전트의 데이터 분석이 완료되었습니다."
    }
    
    # 매핑된 메시지 반환 또는 기본 메시지 반환
    return agent_messages.get(agent, {}).get(status, default_messages[status])

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
    stock_code: Optional[str] = Field(None, description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    stock_info: Optional[Dict[str, Any]] = Field(None, description="종목 관련 추가 정보")


class ChatSessionUpdateRequest(BaseModel):
    """채팅 세션 업데이트 요청 모델"""
    title: Optional[str] = Field(None, description="채팅 세션 제목")
    stock_code: Optional[str] = Field(None, description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    stock_info: Optional[Dict[str, Any]] = Field(None, description="종목 관련 추가 정보")
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
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    stock_info: Optional[Dict[str, Any]] = None
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
    content_expert: Optional[str] = None
    agent_results: Optional[Dict[str, Any]] = None
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


class ChatMessageStreamRequest(BaseModel):
    """채팅 메시지 스트리밍 요청 모델"""
    message: str = Field(..., description="메시지 내용")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")
    is_follow_up: bool = Field(False, description="후속질문 여부")


class ChatMemoryResponse(BaseResponse):
    """채팅 메모리 응답 모델"""
    messages: List[Dict[str, Any]]
    total: int


class PDFResponse(BaseResponse):
    """PDF 다운로드 응답 모델"""
    download_url: str = Field(..., description="PDF 다운로드 URL")
    file_name: str = Field(..., description="PDF 파일 이름")
    expires_at: str = Field(..., description="URL 만료 시간")


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
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            stock_info=request.stock_info
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

# # 현재는 안쓰는 함수
# @chat_router.post("/sessions/{chat_session_id}/messages", response_model=ChatMessageResponse)
# async def create_chat_message(
#     chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
#     request: ChatMessageCreateRequest = Body(...),
#     db: AsyncSession = Depends(get_db_async),
#     current_session: Session = Depends(get_current_session),
#     stock_rag_service: StockRAGService = Depends(get_stock_rag_service)
# ) -> ChatMessageResponse:
#     """새 채팅 메시지를 생성하고 응답을 생성합니다."""
#     try:
#         # 현재는 안쓰는 함수
#         logger.info(f"create_chat_message 호출: {request}")
#         # 세션 존재 여부 확인
#         session_data = await ChatService.get_chat_session(
#             db=db,
#             session_id=chat_session_id,
#             user_id=current_session.user_id
#         )
        
#         if not session_data:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="채팅 세션을 찾을 수 없습니다."
#             )
        
#         logger.info(f"session_data: {session_data}")
        
#         # 메모리 관리자 인스턴스 가져오기
#         from common.core.memory import chat_memory_manager
        
#         # 사용자 메시지 저장
#         user_message = await ChatService.create_chat_message(
#             db=db,
#             chat_session_id=chat_session_id,
#             role="user",
#             content=request.message,
#             stock_code=request.stock_code,
#             stock_name=request.stock_name
#         )
#         logger.info(f"user_message: {user_message}")
        
#         # 메모리에 사용자 메시지 추가
#         await chat_memory_manager.add_user_message(str(chat_session_id), request.message)
        
#         # 대화 히스토리 가져오기
#         conversation_history = await chat_memory_manager.get_messages(str(chat_session_id))
#         logger.info(f"대화 히스토리 로드 완료: {len(conversation_history)}개 메시지")
        
#         # LLM으로 응답 생성
#         # StockRAGService를 사용하여 응답 생성 (대화 히스토리 포함)
#         rag_result = await stock_rag_service.analyze_stock(
#             query=request.message,
#             stock_code=request.stock_code,
#             stock_name=request.stock_name,
#             session_id=str(current_session.id),
#             user_id=str(current_session.user_id),
#             conversation_history=conversation_history
#         )

#         # 응답 정보 추출
#         answer = rag_result.get('answer', '')
#         answer_expert = rag_result.get('answer_expert', '')

#         # # 메타데이터 설정
#         # metadata = {
#         #     "rag_result": {
#         #         "trace_id": rag_result.get("trace_id"),
#         #         # 필요한 경우 추가 메타데이터 설정
#         #     }
#         # }
#         # 랜덤 숫자.
#         #answer = f"어시스턴트 응답 저장 : {random.randint(1, 1000000)}"
#         metadata = ""
#         #logger.info(f"어시스턴트 응답 저장 : {answer}")
        
#         # 메모리에 AI 응답 추가
#         await chat_memory_manager.add_ai_message(str(chat_session_id), answer)
        
#         # 어시스턴트 응답 저장
#         logger.debug("[STREAM_CHAT] 어시스턴트 응답 저장 중...")
#         assistant_message = await ChatService.create_chat_message(
#             db=db,
#             message_id=user_message["id"],
#             chat_session_id=chat_session_id,
#             role="assistant",
#             content=answer,
#             content_expert=answer_expert,
#             stock_code=request.stock_code,
#             stock_name=request.stock_name,
#             metadata=metadata,
#             agent_results=rag_result.get("agent_results", {})
#         )
#         # 어시스턴트 메시지 ID 저장
#         assistant_message_id = str(assistant_message["id"])
#         logger.info(f"[STREAM_CHAT] 어시스턴트 응답 저장 완료: {assistant_message_id}")
        
#         # 세션에도 agent_results 저장
#         logger.debug("[STREAM_CHAT] 세션에 에이전트 결과 저장 중...")
        
#         # 업데이트할 데이터 준비
#         update_data = {}
        
#         # agent_results 데이터를 해당 세션에 추가
#         update_data["agent_results"] = rag_result.get("agent_results", {})
        
#         # 기존 세션 데이터 확인
#         if not session_data.get("stock_code") and request.stock_code:
#             update_data["stock_code"] = request.stock_code
            
#         if not session_data.get("stock_name") and request.stock_name:
#             update_data["stock_name"] = request.stock_name
        
#         logger.debug(f"[STREAM_CHAT] 업데이트할 세션 데이터: {list(update_data.keys())}")
        
#         # 세션 업데이트
#         await ChatService.update_chat_session(
#             db=db,
#             session_id=chat_session_id,
#             user_id=current_session.user_id,
#             update_data=update_data
#         )
#         logger.info("[STREAM_CHAT] 세션에 에이전트 결과 저장 완료")
        
#         assistant_message["ok"] = True
#         assistant_message["status_message"] = "정상 응답 완료"
#         logger.info(f"어시스턴트 응답 완료")
#         return ChatMessageResponse(**assistant_message)
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error("채팅 메시지 생성 중 오류 발생: {}", str(e), exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"채팅 메시지 생성 중 오류 발생: {str(e)}"
#         )


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


@chat_router.post("/sessions/{chat_session_id}/messages/stream")
async def stream_chat_message(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    request: ChatMessageStreamRequest = Body(...),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session),
    stock_rag_service: StockRAGService = Depends(get_stock_rag_service)
) -> EventSourceResponse:
    """
    채팅 메시지를 생성하고 처리 과정을 스트리밍합니다.
    각 에이전트의 시작과 종료 시점에 이벤트를 전송합니다.
    최종 응답은 토큰 단위로 스트리밍됩니다.
    """
    logger.info("[STREAM_CHAT] 스트리밍 메시지 처리 시작: 채팅 세션 ID={}, 메시지='{}', 후속질문={}", 
                chat_session_id, request.message, request.is_follow_up)
    try:
        refresh_agent_llm_cache()
        # test code
        stock_info_service = StockInfoService()
        stock_info = await stock_info_service.get_stock_by_code(request.stock_code)
        logger.info(f"[STREAM_CHAT] 종목 정보: {stock_info}")
        # 먼저 채팅 세션 확인
        logger.debug("[STREAM_CHAT] 채팅 세션 확인 중...")
        session_data = await ChatService.get_chat_session(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id
        )
        
        if not session_data:
            logger.warning("[STREAM_CHAT] 채팅 세션을 찾을 수 없음: 세션 ID={}", chat_session_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="채팅 세션을 찾을 수 없습니다."
            )
        # falst일때 세션의 agent result를 덮어쓰니까 false일때 한번 더 정확하게 체크해야겠네.
        is_follow_up = request.is_follow_up
        if not request.is_follow_up:
            # 첫 질문일때는, 진짜 첫질문이 맞는지 다시 한번 체크
            messages = await ChatService.get_chat_messages(
                db=db,
                session_id=chat_session_id,
                user_id=current_session.user_id,
                limit=1,
                offset=0
            )
            ll = len(messages)
            if ll >= 2: # 2개 이상이어야 진짜 후속질문 모드.
                logger.info("[STREAM_CHAT] 후속질문 모드 시작")
                is_follow_up = True
            else:
                logger.info("[STREAM_CHAT] 첫 질문이 맞음")
                is_follow_up = False

        # 후속질문이면. 세션에서 에이전트 결과물 꺼냄
        agent_results = {}
        if is_follow_up:
            agent_results = await ChatService.get_chat_session_agent_results(
                db=db,
                session_id=chat_session_id,
                user_id=current_session.user_id
            )
            logger.info(f"[STREAM_CHAT] 후속질문 모드 세션 에이전트 결과: {agent_results.get('report_analyzer', {})}")

        # 응답 스트리밍용 이벤트 큐
        streaming_queue = asyncio.Queue()
        # 응답 생성 완료 이벤트
        response_done_event = asyncio.Event()
        # 최종 응답 저장 변수
        full_response = ""
        # 응답 메타데이터
        response_metadata = {}
        # 어시스턴트 메시지 ID
        assistant_message_id = uuid4()
        
        # JSON 직렬화를 위한 커스텀 인코더 (datetime 객체 처리)
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)
            
        # 스트리밍 콜백 함수
        async def streaming_callback(chunk: str):
            nonlocal full_response
            # 로깅 추가
            print(f"[{chunk}]", end="", flush=True)
            logger.info(f"[STREAM_CHAT] streaming_callback 호출됨: 청크 길이={len(chunk)}")
            # 청크 내용을 큐에 추가
            await streaming_queue.put(json.dumps({
                "event": "token",
                "data": {
                    "token": chunk,
                    "message_id": str(assistant_message_id),
                    "timestamp": time.time()
                }
            }, cls=DateTimeEncoder))
            # 전체 응답에 누적
            full_response += chunk
        
        # 스트리밍 콜백 함수에 이름 부여 (디버깅 용이)
        streaming_callback.__name__ = "streaming_callback_chat"
        logger.info(f"[STREAM_CHAT] 스트리밍 콜백 함수 생성 완료: {streaming_callback.__name__}, id={id(streaming_callback)}")
        
        # 비동기 생성기 함수 정의
        async def event_generator():
            nonlocal full_response, response_metadata, assistant_message_id, agent_results
            
            
            
            # 초기 이벤트 전송
            #logger.info("[STREAM_CHAT] 초기 이벤트 전송")
            yield json.dumps({
                "event": "start",
                "data": {
                    "message": "질문 처리를 시작합니다.",
                    "timestamp": time.time()
                }
            })
            
            # 처리 시작 시간 저장
            start_time = time.time()
            
            # 사용자 메시지 저장
            logger.debug("[STREAM_CHAT] 사용자 메시지 저장 중...")
            user_message = await ChatService.create_chat_message(
                db=db,
                chat_session_id=chat_session_id,
                role="user",
                content=request.message,
                stock_code=request.stock_code,
                stock_name=request.stock_name
            )
            logger.info("[STREAM_CHAT] 사용자 메시지 저장 완료: {}", user_message["id"])
            
            # 메모리에 사용자 메시지 추가
            await chat_memory_manager.add_user_message(str(chat_session_id), request.message)
            
            # 스트리밍 콜백을 설정하고 질문 처리 시작
            #logger.info("[STREAM_CHAT] analyze_stock 태스크 시작 (스트리밍 콜백 포함)")
            session_key = str(current_session.id)
            logger.info(f"[STREAM_CHAT] 세션 키: {session_key}, 채팅 세션 ID: {chat_session_id}")
            
            # 태스크 생성 및 시작
            task = asyncio.create_task(
                stock_rag_service.analyze_stock(
                    query=request.message,
                    stock_code=request.stock_code,
                    stock_name=request.stock_name,
                    session_id=session_key,
                    user_id=current_session.user_id,
                    chat_session_id=str(chat_session_id),
                    is_follow_up=request.is_follow_up,  # 후속질문 여부 전달
                    agent_results=agent_results
                    #streaming_callback=streaming_callback  # 스트리밍 콜백 전달
                )
            )
            
            
            # 상태 추적을 위한 이전 상태 저장 변수
            prev_status = {}
            # 응답 시작 여부
            response_started = False
            
            check_count = 0
            
            # 2개의 동시 작업 생성: 상태 모니터링 및 응답 스트리밍
            async def monitor_status():
                nonlocal prev_status, check_count, response_started
                status_events = []  # 이벤트를 저장할 리스트
                
                while not task.done():
                    await asyncio.sleep(0.5)  # 0.5초마다 상태 확인
                    check_count += 1
                    
                    if check_count % 10 == 0:  # 5초마다 로그
                        logger.debug("[STREAM_CHAT] 처리 대기 중... (경과: {:.1f}초)", time.time() - start_time)
                    
                    # 처리 상태 확인
                    graph = stock_rag_service.graph
                    state = None
                    
                    try:
                        # 현재 세션의 처리 상태 가져오기
                        if hasattr(graph, 'current_state') and graph.current_state:
                            state = graph.current_state.get(session_key, {})
                        
                        if state and 'processing_status' in state:
                            processing_status = state['processing_status']
                            
                            # 이전 상태와 비교하여 변경된 부분 확인
                            for agent, status in processing_status.items():
                                if agent not in prev_status or prev_status[agent] != status:
                                    elapsed = time.time() - start_time
                                    # 상태 변경 이벤트 전송
                                    event_data = {
                                        "agent": agent,
                                        "status": status,
                                        "timestamp": time.time(),
                                        "elapsed": elapsed
                                    }
                                    
                                    # 이벤트를 직접 yield하지 않고 큐에 전송
                                    await streaming_queue.put(json.dumps({
                                        "event": "agent_status",
                                        "data": event_data
                                    }, cls=DateTimeEncoder))
                                    
                                    # 에이전트 시작 또는 완료 특별 이벤트
                                    if status == "processing":
                                        logger.info("[STREAM_CHAT] 에이전트 시작: {} (경과: {:.2f}초)", agent, elapsed)
                                        
                                        # 에이전트 이름에 따른 사용자 친화적인 메시지 매핑
                                        user_friendly_message = get_user_friendly_agent_message(agent, "start")
                                        
                                        await streaming_queue.put(json.dumps({
                                            "event": "agent_start",
                                            "data": {
                                                "agent": agent,
                                                "message": user_friendly_message,
                                                "timestamp": time.time(),
                                                "elapsed": elapsed
                                            }
                                        }, cls=DateTimeEncoder))
                                    elif status in ["completed", "completed_with_default_plan", "completed_no_data"]:
                                        logger.info("[STREAM_CHAT] 에이전트 완료: {} (경과: {:.2f}초)", agent, elapsed)
                                        
                                        # 에이전트 이름에 따른 사용자 친화적인 메시지 매핑
                                        user_friendly_message = get_user_friendly_agent_message(agent, "complete")
                                        
                                        await streaming_queue.put(json.dumps({
                                            "event": "agent_complete",
                                            "data": {
                                                "agent": agent,
                                                "message": user_friendly_message,
                                                "timestamp": time.time(),
                                                "elapsed": elapsed
                                            }
                                        }, cls=DateTimeEncoder))
                                        
                                        # response_formatter가 시작되면 응답 스트리밍 단계 시작 알림
                                        if agent == "response_formatter" and status == "processing" and not response_started:
                                            response_started = True
                                            #logger.info("[STREAM_CHAT] 응답 스트리밍 단계 시작")
                                            await streaming_queue.put(json.dumps({
                                                "event": "response_start",
                                                "data": {
                                                    "message": "응답 생성을 시작합니다.",
                                                    "timestamp": time.time(),
                                                    "elapsed": elapsed
                                                }
                                            }, cls=DateTimeEncoder))
                            
                            # 현재 상태를 이전 상태로 저장
                            prev_status = processing_status.copy()
                    except Exception as e:
                        logger.error("[STREAM_CHAT] 처리 상태 확인 중 오류: {}", str(e))
                
                logger.info("[STREAM_CHAT] 상태 모니터링 종료")
            
            async def stream_response():
                nonlocal response_started
                
                # 응답 토큰 스트리밍
                while not task.done() or not streaming_queue.empty():
                    try:
                        # 0.1초 대기 후 큐에서 토큰 가져오기 시도
                        try:
                            event_data = await asyncio.wait_for(streaming_queue.get(), timeout=0.1)
                            print(f"{event_data}", end="", flush=True)
                            # SSE 형식으로 데이터 전송 (data: 접두사 추가)
                            yield f"{event_data}\n\n"
                            streaming_queue.task_done()
                        except asyncio.TimeoutError:
                            # 타임아웃은 무시하고 계속 진행
                            pass
                    except Exception as e:
                        logger.error(f"[STREAM_CHAT] 응답 스트리밍 중 오류: {str(e)}")
                
                logger.info("[STREAM_CHAT] 응답 스트리밍 종료")
            
            # monitor_status 실행 (비동기 태스크로 실행)
            asyncio.create_task(monitor_status())
            
            # stream_response는 제너레이터로 사용
            async for event_data in stream_response():
                if event_data:  # None이 아닌 결과만 전달
                    yield event_data
            
            try:
                # 태스크 완료 대기
                result = await task
                total_time = time.time() - start_time
                
                # 결과에서 요약 추출
                summary = result.get("summary", "")
                # 전체 응답이 스트리밍을 통해 구성되었음
                answer = full_response or result.get("answer", "처리가 완료되었으나 응답을 찾을 수 없습니다.")
                
                logger.info("[STREAM_CHAT] 응답 생성 완료 (총 소요시간: {:.2f}초, 응답 길이: {}자)", 
                           total_time, len(answer))
                
                # 메모리에 AI 응답 추가
                await chat_memory_manager.add_ai_message(str(chat_session_id), answer)
                
                # 메타데이터 설정
                metadata = {
                    "processing_time": total_time,
                    "agents_used": list(prev_status.keys()) if prev_status else [],
                    "responseId": str(uuid4())
                }
                response_metadata = metadata
                
                agent_results = result.get("agent_results", {})
                
                # agent_results에서 report_analyzer 결과 로깅
                if "report_analyzer" in agent_results:
                    logger.info(f"[STREAM_CHAT] report_analyzer 결과: {agent_results.get('report_analyzer', {}).get('status', '')}")
                
                # 에이전트 응답 저장
                logger.debug("[STREAM_CHAT] 어시스턴트 응답 저장 중...")
                assistant_message = await ChatService.create_chat_message(
                    db=db,
                    message_id=assistant_message_id,
                    chat_session_id=chat_session_id,
                    role="assistant",
                    content=answer,
                    content_expert=summary,
                    stock_code=request.stock_code,
                    stock_name=request.stock_name,
                    metadata=metadata,
                )
                # 어시스턴트 메시지 ID 저장
                assistant_message_id = str(assistant_message["id"])
                logger.info(f"[STREAM_CHAT] 어시스턴트 응답 저장 완료: {assistant_message_id}")
                
                # 첫 질문인 경우에만 세션에 정보 저장.
                if not is_follow_up:
                    # 세션에도 agent_results 저장
                    logger.debug("[STREAM_CHAT] 세션에 에이전트 결과 저장 중...")
                    
                    # 업데이트할 데이터 준비
                    update_data = {}
                    
                    # agent_results 데이터를 해당 세션에 추가
                    update_data["agent_results"] = agent_results
                    
                    # 기존 세션 데이터 확인
                    if not session_data.get("stock_code") and request.stock_code:
                        update_data["stock_code"] = request.stock_code
                        
                    if not session_data.get("stock_name") and request.stock_name:
                        update_data["stock_name"] = request.stock_name
                    
                    logger.debug(f"[STREAM_CHAT] 업데이트할 세션 데이터: {list(update_data.keys())}")
                    
                    # 세션 업데이트
                    await ChatService.update_chat_session(
                        db=db,
                        session_id=chat_session_id,
                        user_id=current_session.user_id,
                        update_data=update_data
                    )
                    logger.info("[STREAM_CHAT] 세션에 에이전트 결과 저장 완료")
                
                # 완료 이벤트 전송
                logger.info("[STREAM_CHAT] 완료 이벤트 전송")
                complete_data = json.dumps({
                    'event': 'complete',
                    'data': {
                        'message': '처리가 완료되었습니다.',
                        'response': answer,
                        'response_expert': summary,
                        'message_id': assistant_message_id,
                        'metadata': metadata,
                        'timestamp': time.time(),
                        'elapsed': total_time
                    }
                }, cls=DateTimeEncoder)
                yield f"{complete_data}\n\n"
                
            except Exception as e:
                logger.error("[STREAM_CHAT] 결과 처리 중 오류: {}", str(e), exc_info=True)
                
                # 오류 메시지 저장
                error_message = f"메시지 처리 중 오류가 발생했습니다"
                
                # 응답이 부분적으로 생성되었다면 그것을 저장
                if full_response:
                    answer_to_save = full_response + "\n\n[오류로 인해 응답이 중단되었습니다]"
                else:
                    answer_to_save = error_message
                
                await ChatService.create_chat_message(
                    db=db,
                    chat_session_id=chat_session_id,
                    role="assistant",
                    content=answer_to_save,
                    stock_code=request.stock_code,
                    stock_name=request.stock_name,
                    metadata={"error": str(e)}
                )
                
                # 오류 이벤트 전송
                logger.error("[STREAM_CHAT] 오류 이벤트 전송: {}", error_message)
                error_data = json.dumps({
                    'event': 'error',
                    'data': {
                        'message': error_message,
                        'timestamp': time.time(),
                        'elapsed': time.time() - start_time
                    }
                }, cls=DateTimeEncoder)
                yield f"data: {error_data}\n\n"
        
        # EventSourceResponse 반환
        logger.info("[STREAM_CHAT] EventSourceResponse 설정 및 반환")
        return EventSourceResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Nginx 프록시 버퍼링 비활성화
            }
        )
        
    except Exception as e:
        logger.error("[STREAM_CHAT] 채팅 메시지 스트리밍 중 오류 발생: {}", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채팅 메시지 스트리밍 중 오류 발생: {str(e)}"
        )

@chat_router.delete("/sessions/{chat_session_id}/memory", response_model=BaseResponse)
async def clear_chat_memory(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> BaseResponse:
    """채팅 세션의 대화 메모리를 초기화합니다."""
    try:
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
        
        # 메모리 관리자 인스턴스 가져오기
        from common.core.memory import chat_memory_manager
        
        # 대화 메모리 초기화
        success = await chat_memory_manager.clear_memory(str(chat_session_id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="대화 메모리 초기화 중 오류가 발생했습니다."
            )
        
        logger.info(f"채팅 세션 {chat_session_id}의 메모리가 초기화되었습니다.")
        
        return BaseResponse(
            ok=True,
            status_message="채팅 세션의 메모리가 성공적으로 초기화되었습니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"대화 메모리 초기화 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대화 메모리 초기화 중 오류 발생: {str(e)}"
        ) 

@chat_router.get("/sessions/{chat_session_id}/memory", response_model=ChatMemoryResponse)
async def get_chat_memory(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    limit: int = Query(10, ge=1, le=20, description="조회할 최대 메시지 수"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> ChatMemoryResponse:
    """채팅 세션의 대화 메모리를 조회합니다."""
    try:
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
        
        # 메모리 관리자 인스턴스 가져오기
        from common.core.memory import chat_memory_manager
        
        # 대화 메모리 조회
        messages = await chat_memory_manager.get_messages_as_dict(str(chat_session_id), limit)
        
        logger.info(f"채팅 세션 {chat_session_id}의 메모리 조회 완료: {len(messages)}개 메시지")
        
        return ChatMemoryResponse(
            ok=True,
            status_message="채팅 세션의 메모리 조회가 완료되었습니다.",
            messages=messages,
            total=len(messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"대화 메모리 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대화 메모리 조회 중 오류 발생: {str(e)}"
        ) 

class PDFRequest(BaseModel):
    expert_mode: bool = False

@chat_router.post("/sessions/{chat_session_id}/save_pdf", response_model=PDFResponse)
async def save_chat_to_pdf(
    chat_session_id: UUID = Path(..., description="채팅 세션 ID"),
    pdf_request: PDFRequest = Body(...),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> PDFResponse:
    """채팅 세션의 메시지를 PDF로 저장하고 다운로드 URL을 생성합니다."""
    try:
        logger.info(f"PDF 생성 시작: {chat_session_id}, expert_mode: {pdf_request.expert_mode}")
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
        
        # 메시지 목록 조회 (모든 메시지)
        messages = await ChatService.get_chat_messages(
            db=db,
            session_id=chat_session_id,
            user_id=current_session.user_id,
            limit=1000,  # 충분히 큰 제한값 설정
            offset=0
        )
        
        logger.info(f"메시지 목록 조회 완료: {len(messages)}개 메시지")
        
        # PDF 생성 서비스 호출
        from stockeasy.services.pdf_service import PDFService
        pdf_service = PDFService()
        logger.info(f"PDF 생성 서비스 초기화 완료")
        # PDF 생성
        pdf_result = await pdf_service.generate_chat_pdf(
            chat_session=session_data,
            messages=messages,
            user_id=str(current_session.user_id),
            expert_mode=pdf_request.expert_mode
        )
        
        logger.info(f"PDF 생성 완료: {pdf_result['file_name']}")
        
        return PDFResponse(
            ok=True,
            status_message="PDF 생성 완료",
            download_url=pdf_result["download_url"],
            file_name=pdf_result["file_name"],
            expires_at=pdf_result["expires_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 생성 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF 생성 중 오류 발생: {str(e)}"
        ) 