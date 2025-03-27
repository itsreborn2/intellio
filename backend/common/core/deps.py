from typing import  Optional, TYPE_CHECKING
from uuid import  uuid4

from fastapi import Depends, HTTPException, status, Cookie, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
# 순환 참조 방지를 위해 직접 임포트하지 않고, 실제 사용 시점에 지연 임포트
# from common.services.embedding import EmbeddingService
from common.core.database import get_db_async
from common.core.database import AsyncSessionLocal
from common.services.user import UserService
from common.services.vector_store_manager import VectorStoreManager

from common.models.user import Session
from common.schemas.user import SessionBase
from common.core.exceptions import AuthenticationRedirectException
#import logging
from loguru import logger
from common.core.config import settings

# 타입 힌트용 조건부 임포트
if TYPE_CHECKING:
    from common.services.embedding import EmbeddingService

#logger = logging.getLogger(__name__)

async def get_db():
    """비동기 데이터베이스 세션 프로바이더"""
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()

async def get_current_session(
    session_id: Optional[str] = Cookie(None),
    response: Response = None,
    db: AsyncSession = Depends(get_db_async)
) -> Session:
    """현재 세션 가져오기"""
    try:
        logger.info(f'세션 처리 시작 - 세션 ID: {session_id}')
        user_service = UserService(db)

        # 기존 세션이 있는 경우
        if session_id:
            session = await user_service.get_active_session(session_id)
            if session:
                logger.info(f'유효한 세션 확인: {session.id}')
                return session
        logger.warning('세션이 없거나 만료됨')
        #status_code = status.HTTP_401_UNAUTHORIZED
        raise AuthenticationRedirectException(f'{settings.INTELLIO_URL}/error')

    except AuthenticationRedirectException:
        raise
    except Exception as e:
        logger.error(f'세션 처리 중 오류 발생: {str(e)}', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="세션을 처리할 수 없습니다."
        )

async def get_current_user_uuid(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
) -> Session:
    """현재 인증된 사용자 가져오기"""
    if not session or not session.is_authenticated or not session.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증되지 않은 사용자입니다."
        )
    return session.user.id

async def get_user_service(
    db: AsyncSession = Depends(get_db_async)
) -> UserService:
    """사용자 서비스 의존성"""
    return UserService(db)

async def get_embedding_service():
    """임베딩 서비스 의존성 - 지연 임포트 사용"""
    # 함수 내부에서 임포트하여 순환 참조 방지
    from common.services.embedding import EmbeddingService
    return EmbeddingService()

