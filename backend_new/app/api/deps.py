from typing import Generator, Annotated
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request

from app.core.database import SessionLocal, AsyncSessionLocal
from app.services.user import UserService
from app.models.user import User
from app.services.document import DocumentService
from app.services.rag import RAGService
from app.services.session import SessionService

def get_db() -> Generator[Session, None, None]:
    """동기 DB 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db() -> AsyncSession:
    """비동기 DB 세션 의존성"""
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_async_db)
) -> User:
    """현재 사용자 가져오기 (로그인/비로그인)"""
    # TODO: 나중에 로그인 구현시 여기에 토큰 체크 로직 추가
    user_service = UserService(session)
    return await user_service.get_or_create_anonymous_user(request.client.host)

def get_document_service(db: AsyncSession = Depends(get_async_db)) -> DocumentService:
    """문서 서비스 의존성"""
    return DocumentService(db)

def get_session_service(db: AsyncSession = Depends(get_async_db)) -> SessionService:
    """세션 서비스 의존성"""
    return SessionService(db)

async def get_rag_service(db: AsyncSession = Depends(get_async_db)) -> RAGService:
    """RAG 서비스 의존성"""
    service = RAGService()
    await service.initialize(db)
    return service

# Type annotations for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
AsyncDB = Annotated[AsyncSession, Depends(get_async_db)]
DocumentService = Annotated[DocumentService, Depends(get_document_service)]
SessionService = Annotated[SessionService, Depends(get_session_service)]
RAGService = Annotated[RAGService, Depends(get_rag_service)]
