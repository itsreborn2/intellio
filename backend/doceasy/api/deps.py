from typing import Any, Optional
from requests import Session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from common.core.database import get_db_async
from common.core.deps import get_current_session

from doceasy.services.document import DocumentService
from doceasy.services.rag import RAGService 
from doceasy.services.project import ProjectService

def get_document_service(db: AsyncSession = Depends(get_db_async)) -> DocumentService:
    """문서 서비스 의존성"""
    return DocumentService(db)

# def get_session_service(db: AsyncSession = Depends(get_db_async)) -> SessionService:
#     """세션 서비스 의존성"""
#     return SessionService(db)


async def get_rag_service(
    db: AsyncSession = Depends(get_db_async),
    session: Optional[Session] = Depends(get_current_session)
) -> Any:
    """RAG 서비스 의존성"""
    
    service = RAGService()
    await service.initialize(db, session=session)
    return service

async def get_project_service(db: AsyncSession = Depends(get_db_async)) -> Any:
    """프로젝트 서비스 의존성"""
    return ProjectService(db)
