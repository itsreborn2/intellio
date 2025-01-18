"""RAG 검색 API 라우터"""

from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag import RAGService
from app.api import deps
from app.schemas.table_response import TableResponse, TableHeader
from app.schemas.document import DocumentQueryRequest
from app.core.database import get_db
from app.schemas.rag import RAGQuery, RAGResponse
from app.models.user import Session
from app.core.deps import get_current_session

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

class FillEmptyCellsRequest(BaseModel):
    """빈 셀 채우기 요청"""
    header: TableHeader  # 현재 칼럼 헤더
    document_ids: List[str]  # 빈 셀이 있는 문서 ID 목록

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

@router.post("/table/search", response_model=TableResponse)
async def table_search(
    request: TableQueryRequest,
    session: Session = Depends(get_current_session),
    rag_service: RAGService = Depends(deps.get_rag_service),
    db: AsyncSession = Depends(get_db)
) -> TableResponse:
    """테이블 모드 검색 및 질의응답"""
    try:

        logger.info(f"테이블 검색 요청 - 쿼리: {request.query}, 문서 ID: {request.document_ids}")
        
        # 문서 접근 권한 확인
        # if request.document_ids:
        #     for doc_id in request.document_ids:
        #         if not await rag_service.verify_document_access(doc_id):
        #             raise HTTPException(
        #                 status_code=404,
        #                 detail=f"문서를 찾을 수 없거나 접근할 수 없습니다: {doc_id}"
        #             )

        result = await rag_service.query(
            query=request.query,
            mode=request.mode,
            document_ids=request.document_ids,
            user_id=session.user_id,
            project_id=request.project_id
        )
        
        logger.info(f"테이블 검색 완료 : {result}")
        return result
        
    except Exception as e:
        logger.error(f"테이블 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"테이블 검색 처리 중 오류 발생: {str(e)}"
        )

@router.post("", response_model=Union[Dict[str, Any], TableResponse])
async def query_rag(
    query: RAGQuery,
    db: AsyncSession = Depends(get_db)
):
    
    """RAG 쿼리 처리"""
    service = RAGService()
    await service.initialize(db)
    
    # 문서 접근 권한 확인
    if query.document_ids:
        for doc_id in query.document_ids:
            if not await service.verify_document_access(doc_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"문서를 찾을 수 없거나 접근할 수 없습니다: {doc_id}"
                )
    
    return await service.query(
        query=query.query,
        mode=query.mode,
        document_ids=query.document_ids,
        user_id=query.user_id,
        project_id=query.project_id
    )

@router.post("/chat")
async def chat_search(
    request: ChatRequest,
    rag_service: RAGService = Depends(deps.get_rag_service)
):
    """채팅 모드 검색 및 질의응답"""
    try:
        logger.info(f"채팅 검색 요청 - 메시지: {request.message}, 문서 ID: {request.document_ids}")
        result = await rag_service.query(
            query=request.message,
            mode="chat",
            document_ids=request.document_ids
        )
        answer = result.get('answer')
        logger.info(f"채팅 검색 완료 - 답변: {result.get('answer')}")
        return answer
    except Exception as e:
        logger.error(f"채팅 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"채팅 검색 중 오류 발생: {str(e)}"
        )

@router.post("/table/fill-empty-cells")
async def fill_empty_cells(
    request: FillEmptyCellsRequest,
    rag_service: RAGService = Depends(deps.get_rag_service)
):
    """빈 셀 채우기"""
    try:
        result = await rag_service.fill_empty_cells(
            header=request.header,
            document_ids=request.document_ids
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"빈 셀 채우기 중 오류 발생: {str(e)}"
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
