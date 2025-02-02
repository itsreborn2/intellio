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
#logger.setLevel(logging.DEBUG)

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
    try:
        logger.info(f'세션 처리 시작 - 세션 ID: {session_id}')
        user_service = UserService(db)

        # 기존 세션이 있는 경우
        if session_id:
            session = await user_service.get_active_session(session_id)
            if session:
                logger.info(f'유효한 세션 확인: {session.session_id}')
                return session
            logger.info('세션이 없거나 만료됨')

        # 새 세션 생성
        logger.info('새 세션 생성 시작')
        new_session_id = str(uuid4())
        session_create = SessionCreate(
            session_id=new_session_id,
            is_anonymous=True
        )
        
        session = await user_service.create_session(session_create)
        
        # 쿠키 설정
        if response:
            logger.info(f'새 세션 쿠키 설정: {new_session_id}')
            response.set_cookie(
                key="session_id",
                value=new_session_id,
                max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,  # 설정된 일수를 초로 변환
                httponly=True,
                secure=True,     # HTTPS 전용
                samesite="lax"   # CSRF 방지 (lax로 변경하여 일반적인 링크 이동 허용)
            )
        
        return session

    except Exception as e:
        logger.error(f'세션 처리 중 오류 발생: {str(e)}', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="세션을 처리할 수 없습니다."
        )

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
