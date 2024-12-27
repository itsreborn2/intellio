from typing import AsyncGenerator, Optional, Type
from uuid import UUID

from fastapi import Depends, HTTPException, status, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services.user import UserService
from app.models.user import Session
from app.services.project import ProjectService
from app.services.document import DocumentService

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 의존성"""
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_session(
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
) -> Session:
    """현재 세션 가져오기"""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="세션이 존재하지 않습니다."
        )

    user_service = UserService(db)
    session = await user_service.get_active_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 세션입니다."
        )
    
    return session

async def get_current_user(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
) -> Session:
    """현재 인증된 사용자 가져오기"""
    if not session.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증되지 않은 사용자입니다."
        )
    return session

def get_project_service(
    db: AsyncSession = Depends(get_db)
) -> ProjectService:
    """프로젝트 서비스 의존성"""
    return ProjectService(db)

def get_document_service(
    db: AsyncSession = Depends(get_db)
) -> DocumentService:
    """문서 서비스 의존성"""
    return DocumentService(db)
