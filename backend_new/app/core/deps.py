from typing import AsyncGenerator, Optional, Type
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, status, Cookie, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services.user import UserService
from app.models.user import Session
from app.schemas.user import SessionCreate
from app.services.project import ProjectService
from app.services.document import DocumentService
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 의존성"""
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_session(
    session_id: Optional[str] = Cookie(None),
    response: Response = None,
    db: AsyncSession = Depends(get_db)
) -> Session:
    """현재 세션 가져오기"""
    print(f"DB 포트 확인 : {settings.POSTGRES_PORT}")

    logger.info(f'[get_current_session] : {session_id}')
    print(f'[get_current_session] : {session_id}')
    user_service = UserService(db)
    logger.info(f"[get_current_session] 1")
    if not session_id:
        logger.info(f'  => 세션이 존재하지 않습니다.')
        # 새 세션 생성
        session_create = SessionCreate(
            session_id=str(uuid4()),
            is_anonymous=True
        )
        session = await user_service.create_session(session_create)
        
        if response:
            logger.info(f"[get_current_session] 1-1")
            # 세션 ID를 쿠키에 설정
            response.set_cookie(
                key="session_id",
                value=session.session_id,
                max_age=30 * 24 * 60 * 60,  # 30일
                httponly=True,
                secure=True,  # HTTPS 전용
                samesite="strict"  # CSRF 방지 강화
            )
        return session
    logger.info(f"[get_current_session] 2")
    session = await user_service.get_active_session(session_id)
    logger.info(f"[get_current_session] 3")
    if not session:
        logger.info(f'  => 유효하지 않은 세션입니다.')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 세션입니다."
        )
    logger.info(f"final session : ${session}, : id추가 조회 ${session.user_id}")
    return session

async def get_current_user_uuid(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
) -> Session:
    """현재 인증된 사용자 가져오기"""
    if not session or not session.is_authenticated or not session.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증되지 않은 사용자입니다."
        )
    return session.user.id

async def get_user_service(
    db: AsyncSession = Depends(get_db)
) -> UserService:
    """사용자 서비스 의존성"""
    return UserService(db)

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
