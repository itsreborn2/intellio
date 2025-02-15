"""RAG 검색 API 라우터"""

from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.database import get_db_async
from common.models.user import Session
from common.core.deps import get_current_session


from doceasy.services.rag import RAGService
from doceasy.api import deps
from doceasy.schemas.table_response import TableResponse, TableHeader
from doceasy.schemas.document import DocumentQueryRequest
from doceasy.schemas.rag import RAGQuery, RAGResponse



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
        return response

        
    except Exception as e:
        logger.error(f"테이블 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"테이블 검색 처리 중 오류 발생: {str(e)}"
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
        
        
        async def generate_stream():

            
            # AI 모델에 등록하는 콜백 핸들러.
            # AI 모델에 도달하기 전에 예외처리 리턴되는 케이스는 handle_token을 수행하지 않음.
            def handle_token(token: str):

                #logger.info(f"Handling token: {token}")
                print(f"{token}", end="", flush=True)
                #logger.warning(f"handle_token : {token}")
                return f"data: {token}\n\n"

            try:
                # RAG 서비스 초기화
                rag_service = RAGService(handle_token)
                await rag_service.initialize(db)
                rag_service.set_streaming_callback(handle_token)
                
                
                logger.info(f"채팅 검색 요청 - 메시지: {request.message}, 문서 ID: {request.document_ids}")
                
                # 스트리밍 응답 처리
                async for token in rag_service.query_stream(
                    query=request.message,
                    mode="chat",
                    document_ids=request.document_ids
                ):
                    if token is not None:  # None이 아닐 때만 yield
                        # 여기는 handle_token에서 yield 될때, 예외처리 구간에서 도달.
                        yield token

                # 스트리밍 종료 신호
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"스트리밍 생성 중 오류 발생: {str(e)}")
                error_message = f"data: 죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}\n\n"
                yield error_message
                yield "data: [DONE]\n\n"
            
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Encoding": "none",
                "X-Accel-Buffering": "no"  # Nginx 프록시 버퍼링 비활성화
            }
        )
        
    except Exception as e:
        logger.error(f"채팅 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"채팅 검색 중 오류 발생: {str(e)}"
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
