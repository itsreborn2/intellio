"""RAG 검색 API 라우터"""

import json
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
import logging
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import traceback

from common.core.database import get_db_async
from common.models.user import Session
from common.core.deps import get_current_session

from doceasy.services.rag import RAGService
from doceasy.api import deps
from doceasy.schemas.table_response import TableResponse, TableHeader
from doceasy.schemas.document import DocumentQueryRequest
from doceasy.schemas.rag import RAGQuery, RAGResponse
from doceasy.models.chat import ChatHistory

from celery.result import AsyncResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 디버그 로깅 활성화

router = APIRouter(prefix="/rag", tags=["rag"])

class TableQueryRequest(BaseModel):
    """테이블 모드 쿼리 요청"""
    query: str
    mode: str = "table"
    document_ids: List[str]  # 테이블에 표시된 문서 ID 목록
    user_id: str = None
    project_id: str = None

class ChatContext(BaseModel):
    """채팅 컨텍스트"""
    text: str
    score: float

class ChatResponse(BaseModel):
    """채팅 응답"""
    answer: str
    context: List[ChatContext]

class VerifyAccessRequest(BaseModel):
    """RAG 서비스 접근 권한 확인 요청"""
    document_ids: List[str]

class DocumentStatusResponse(BaseModel):
    """문서 상태 응답"""
    document_id: str
    status: str
    error_message: Optional[str] = None
    is_accessible: bool

class ChatRequest(BaseModel):
    """채팅 요청"""
    project_id: str  # 프로젝트 ID
    document_ids: List[str]  # 문서 ID 목록
    message: str  # 사용자 메시지

class StopGenerationRequest(BaseModel):
    """생성 중지 요청"""
    project_id: str

async def stream_response(generator: AsyncGenerator) -> StreamingResponse:
    """SSE 응답 생성"""
    print(generator, end="", flush=True)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Encoding": "none",
        },
    )

@router.post("/table/search", response_model=TableResponse)
async def table_search(
    request: TableQueryRequest,
    session: Session = Depends(get_current_session),
    rag_service: RAGService = Depends(deps.get_rag_service),
    db: AsyncSession = Depends(get_db_async)
) -> TableResponse:
    """테이블 모드 검색 및 질의응답"""
    try:

        logger.info(f"테이블 검색 요청 - 쿼리: {request.query}, 문서 ID: {request.document_ids}, Mode: {request.mode}")
        
        # 사용자 메시지 저장
        user_message = ChatHistory(
            id=str(uuid4()),
            project_id=request.project_id,
            role="user",
            content=request.query
        )
        db.add(user_message)
        await db.commit()
        logger.info(f"사용자 메시지 저장 완료 - ID: {user_message.id}, 내용: {request.query}")

        # 문서 접근 권한 확인
        # if request.document_ids:
        #     for doc_id in request.document_ids:
        #         if not await rag_service.verify_document_access(doc_id):
        #             raise HTTPException(
        #                 status_code=404,
        #                 detail=f"문서를 찾을 수 없거나 접근할 수 없습니다: {doc_id}"
        #             )

        #doc_ids = [UUID(doc_id) for doc_id in request.document_ids]
        response = await rag_service.handle_table_mode(
            query=request.query,
            document_ids=request.document_ids,
            user_id=session.user_id,
            project_id=request.project_id
        )
        logger.info(f"테이블 검색 완료 : {response}")

        #`**${result.columns[0].header.name}** 컬럼이 추가되었습니다. 테이블을 확인해주세요.
        # 스트리밍 완료 후 메시지 저장
        assistant_message_id = str(uuid4())
        assistant_message = ChatHistory(
            id=assistant_message_id,
            project_id=request.project_id,
            role="assistant",
            content=f'**{response.columns[0].header.name}** 컬럼이 추가되었습니다. 테이블을 확인해주세요.'
        )
        db.add(assistant_message)
        await db.commit()
        logger.info(f"AI 응답 저장 완료 - ID: {assistant_message_id}")

        return response

        
    except Exception as e:
        logger.error(f"테이블 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"테이블 검색 처리 중 오류 발생: {str(e)}"
        )

@router.post("/table/search/stream")
async def table_search_stream(
    request: TableQueryRequest,
    session: Session = Depends(get_current_session),
    rag_service: RAGService = Depends(deps.get_rag_service),
    db: AsyncSession = Depends(get_db_async)
) -> EventSourceResponse:
    """테이블 모드 검색 및 질의응답 (스트리밍 방식)"""
    try:
        logger.info(f"테이블 검색 스트리밍 요청 - 쿼리: {request.query}, 문서 ID: {request.document_ids}, Mode: {request.mode}")
        
        # 사용자 메시지 저장
        user_message = ChatHistory(
            id=str(uuid4()),
            project_id=request.project_id,
            role="user",
            content=request.query
        )
        db.add(user_message)
        await db.commit()
        logger.info(f"사용자 메시지 저장 완료 - ID: {user_message.id}, 내용: {request.query}")

        # SSE 스트리밍 제너레이터 함수
        async def generate():
            try:
                # 스트리밍 방식으로 테이블 모드 처리
                async for event in rag_service.handle_table_mode_stream(
                    query=request.query,
                    document_ids=request.document_ids,
                    user_id=session.user_id,
                    project_id=request.project_id
                ):
                    # 이벤트 타입과 데이터 추출
                    event_type = event.get("event", "message")
                    event_data = event.get("data", {})
                    
                    # 완료 이벤트인 경우 메시지 저장
                    if event_type == "completed":
                        # 컬럼 이름 가져오기 (헤더 이벤트에서 전송된 데이터)
                        column_name = event_data.get("header_name", "새로운 컬럼")
                        
                        # 응답 메시지 저장
                        assistant_message = ChatHistory(
                            id=str(uuid4()),
                            project_id=request.project_id,
                            role="assistant",
                            content=f'**{column_name}** 컬럼이 추가되었습니다. 테이블을 확인해주세요.'
                        )
                        db.add(assistant_message)
                        await db.commit()
                    
                    # SSE 이벤트 전송(json 형식으로 전송)
                    final_data = {
                        "event": event_type,
                        "data": event_data
                    }
                    ss = json.dumps(final_data, ensure_ascii=False)
                    logger.info("----------------------------------")
                    logger.info(ss)
                    yield ss
                    
                    # 필요한 경우 진행 상황 로깅
                    if event_type != "progress":
                        logger.info(f"테이블 검색 이벤트 전송: {event_type}")
                    
            except Exception as e:
                logger.error(f"스트리밍 처리 중 오류: {str(e)}")
                # 오류 이벤트 전송
                yield {
                    "event": "error",
                    "data": {"message": f"처리 중 오류가 발생했습니다: {str(e)}"}
                }
                raise

        # EventSourceResponse 반환
        return EventSourceResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Encoding": "none",
            }
        )
        
    except Exception as e:
        logger.exception(f"테이블 스트리밍 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"테이블 스트리밍 검색 처리 중 오류 발생: {str(e)}"
        )

@router.post("", response_model=Union[Dict[str, Any], TableResponse])
async def query_rag(
    query: RAGQuery,
    db: AsyncSession = Depends(get_db_async)
):
    
    """RAG 쿼리 처리"""
    # service = RAGService()
    # await service.initialize(db)
    
    # # 문서 접근 권한 확인
    # if query.document_ids:
    #     for doc_id in query.document_ids:
    #         if not await service.verify_document_access(doc_id):
    #             raise HTTPException(
    #                 status_code=404,
    #                 detail=f"문서를 찾을 수 없거나 접근할 수 없습니다: {doc_id}"
    #             )
    
    # return await service.query(
    #     query=query.query,
    #     mode=query.mode,
    #     document_ids=query.document_ids,
    #     user_id=query.user_id,
    #     project_id=query.project_id
    # )
    return None

@router.post("/chat")
async def chat_search(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db_async),
    session: Session = Depends(get_current_session),
):
    """채팅 모드 검색 및 질의응답"""
    try:
        # 사용자 메시지 저장
        user_message = ChatHistory(
            id=str(uuid4()),
            project_id=request.project_id,
            role="user",
            content=request.message
        )
        db.add(user_message)
        await db.commit()
        logger.info(f"사용자 메시지 저장 완료 - ID: {user_message.id}, 내용: {request.message}")

        async def generate_stream():
            # AI 응답을 위한 ID 미리 생성
            assistant_message_id = str(uuid4())
            full_response = ""

            try:
                # RAG 서비스 초기화
                rag_service = RAGService()
                await rag_service.initialize(db)
                
                logger.info(f"채팅 검색 요청 - 메시지: {request.message}, 문서 ID: {request.document_ids}")
                
                # 토큰 버퍼 초기화
                token_buffer = ""
                
                # 스트리밍 응답 처리
                async for token in rag_service.query_stream(
                    query=request.message,
                    mode="chat",
                    document_ids=request.document_ids
                ):
                    if token is not None:
                        full_response += token
                        token_buffer += token
                        
                        # 버퍼가 5글자 이상이면 전송
                        if len(token_buffer) >= 5:
                            yield {
                                "event": "message",
                                "data": token_buffer
                            }
                            print(f"{token_buffer}", end="", flush=True)
                            token_buffer = ""  # 버퍼 초기화

                # 남은 버퍼가 있다면 전송
                if token_buffer:
                    yield {
                        "event": "message",
                        "data": token_buffer
                    }

                # 스트리밍 완료 후 메시지 저장
                assistant_message = ChatHistory(
                    id=assistant_message_id,
                    project_id=request.project_id,
                    role="assistant",
                    content=full_response
                )
                db.add(assistant_message)
                await db.commit()
                logger.info(f"AI 응답 저장 완료 - ID: {assistant_message_id}")

                # 완료 이벤트 전송
                yield {
                    "event": "done",
                    "data": "[DONE]"
                }

            except Exception as e:
                logger.error(f"스트리밍 응답 생성 중 오류 발생: {str(e)}")
                yield {
                    "event": "error",
                    "data": str(e)
                }
            
        return EventSourceResponse(
            generate_stream(),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Nginx 프록시 버퍼링 비활성화
            }
        )
        
    except Exception as e:
        logger.error(f"채팅 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"채팅 검색 중 오류 발생: {str(e)}"
        )

@router.get("/chat/history/{project_id}")
async def get_chat_history(
    project_id: str,
    db: AsyncSession = Depends(get_db_async),
    session: Session = Depends(get_current_session)
) -> List[Dict[str, Any]]:
    """프로젝트별 대화 기록 조회"""
    try:
        logger.info(f"대화 기록 조회 - 프로젝트 ID: {project_id}")
        query = select(ChatHistory).where(
            ChatHistory.project_id == project_id
        ).order_by(ChatHistory.created_at)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        logger.info(f"대화 기록 조회 완료 - 총 {len(messages)}개의 메시지")
        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    except Exception as e:
        logger.error(f"대화 기록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"대화 기록 조회 중 오류 발생: {str(e)}"
        )

@router.post("/verify-access")
async def verify_access(
    request: VerifyAccessRequest,
    rag_service: RAGService = Depends(deps.get_rag_service)
) -> Dict[str, bool]:
    """RAG 서비스 접근 권한 확인
    
    Args:
        request: 문서 ID 목록을 포함한 요청
        
    Returns:
        Dict[str, bool]: 접근 가능 여부
    """
    try:
        logger.info(f"RAG 서비스 접근 권한 확인 - 문서 ID: {request.document_ids}")
        
        # 문서 존재 여부 및 접근 권한 확인
        for doc_id in request.document_ids:
            if not await rag_service.verify_document_access(doc_id):
                logger.warning(f"문서 접근 권한 없음: {doc_id}")
                return {"has_access": False}
        
        logger.info("RAG 서비스 접근 권한 확인 완료")
        return {"has_access": True}
        
    except Exception as e:
        logger.error(f"접근 권한 확인 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"접근 권한 확인 중 오류 발생: {str(e)}"
        )

@router.post("/document-status", response_model=List[DocumentStatusResponse])
async def get_documents_status(
    request: VerifyAccessRequest,
    rag_service: RAGService = Depends(deps.get_rag_service)
) -> List[DocumentStatusResponse]:
    """문서들의 상태 조회
    
    Args:
        request: 문서 ID 목록을 포함한 요청
        
    Returns:
        List[DocumentStatusResponse]: 각 문서의 상태 정보
    """
    try:
        logger.info(f"문서 상태 조회 - 문서 ID: {request.document_ids}")
        
        # 각 문서의 상태 조회
        statuses = []
        for doc_id in request.document_ids:
            status = await rag_service.get_document_status(doc_id)
            statuses.append(status)
        
        logger.info("문서 상태 조회 완료")
        return statuses
        
    except Exception as e:
        logger.error(f"문서 상태 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"문서 상태 조회 중 오류 발생: {str(e)}"
        )

@router.post("/chat/stop")
async def stop_chat_generation(
    request: StopGenerationRequest,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """채팅 메시지 생성 중지"""
    try:
        logger.info(f"메시지 생성 중지 요청 - 프로젝트 ID: {request.project_id}")
        # RAG 서비스 직접 초기화
        rag_service = RAGService()
        await rag_service.initialize(db)
        await rag_service.stop_generation()
        return {"status": "success", "message": "메시지 생성이 중지되었습니다."}
    except Exception as e:
        logger.error(f"메시지 생성 중지 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"메시지 생성 중지 중 오류 발생: {str(e)}"
        )
