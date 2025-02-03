from typing import Generator, Annotated, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from common.core.database import get_db_async

from doceasy.services.document import DocumentService
from doceasy.services.rag import RAGService 

def get_document_service(db: AsyncSession = Depends(get_db_async)) -> DocumentService:
    """문서 서비스 의존성"""
    return DocumentService(db)

# def get_session_service(db: AsyncSession = Depends(get_db_async)) -> SessionService:
#     """세션 서비스 의존성"""
#     return SessionService(db)

async def get_rag_service(db: AsyncSession = Depends(get_db_async)) -> Any:
    """RAG 서비스 의존성"""
    
    service = RAGService()
    await service.initialize(db)
    return service

# # Type annotations for dependency injection
# CurrentUser = Annotated[User, Depends(get_current_user)]
# AsyncDB = Annotated[AsyncSession, Depends(get_async_db)]
# DocumentService = Annotated[DocumentService, Depends(get_document_service)]
# SessionService = Annotated[SessionService, Depends(get_session_service)]
# RAGService = Annotated[Any, Depends(get_rag_service)]  # Any 타입 사용
