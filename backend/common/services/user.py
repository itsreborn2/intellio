from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from uuid import UUID, uuid4
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter

from common.core.security import get_password_hash, verify_password
from common.models.user import User, Session
from common.schemas.user import UserCreate, UserUpdate, SessionBase, SessionUpdate
from common.core.config import settings
import logging

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class UserService:
    """사용자 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_in: UserCreate) -> User:
        """새 사용자 생성"""
        db_user = User(
            id=uuid4(),  # UUID 자동 생성
            email=user_in.email,
            name=user_in.name,
            hashed_password=get_password_hash(user_in.password),
            is_active=True,
            is_superuser=False
        )
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """사용자 인증"""
        user = await self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def get(self, user_id: UUID) -> Optional[User]:
        """사용자 조회"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_oauth(self, provider: str, oauth_id: str) -> Optional[User]:
        """OAuth 제공자와 ID로 사용자 조회"""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.oauth_provider == provider,
                    User.oauth_provider_id == oauth_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def update(self, user_id: UUID, user_in: UserUpdate) -> Optional[User]:
        """사용자 정보 수정"""
        user = await self.get(user_id)
        if not user:
            return None

        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user_id: UUID) -> bool:
        """사용자 삭제"""
        user = await self.get(user_id)
        if not user:
            return False

        await self.db.delete(user)
        await self.db.commit()
        return True

    async def create_oauth_user(self, user_data: dict) -> User:
        """OAuth 사용자 생성"""
        # name이 없거나 None인 경우 이메일의 @ 앞부분을 사용
        if not user_data.get("name"):
            user_data["name"] = user_data["email"].split("@")[0]

        user = User(
            id=uuid4(),
            email=user_data["email"],
            hashed_password=None,
            is_active=True,
            is_superuser=False,
            name=user_data["name"],
            oauth_provider=user_data["oauth_provider"],
            oauth_provider_id=user_data["oauth_provider_id"]
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def create_session(self, session_in: SessionBase) -> Session:
        """새 세션 생성"""
        session_id = uuid4()
        logger.info(f'[create_session] Creating new session with id: {session_id}')

        db_session = Session(
            id=session_id,
            user_id=session_in.user_id,
            user_email=session_in.user_email,
            is_anonymous=session_in.is_anonymous
        )
        self.db.add(db_session)
        await self.db.commit()
        await self.db.refresh(db_session)
        logger.info(f'[create_session] Created session: {db_session}')
        return db_session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """세션 조회"""
        #logger.info(f'[get_session] trying to find session_id: {session_id}')
        query = (
            select(Session)
            .where(Session.id == session_id)
        )
        
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()

        if session:
            logger.info(f'[get_session] associated user: {session.user}')
        return session

    async def get_active_session(self, session_id: str) -> Optional[Session]:
        """활성 세션 조회"""
        try:
            #logger.info(f'[get_active_session] 시작: session_id = {session_id}')
            session = await self.get_session(session_id)
            #logger.info(f'[get_active_session] 세션 조회 결과: {session}')
            
            if not session:
                # 세션이 없다면, 여기서 세션 테이블을 조회해서 1일 이내의 세션 데이터가 있는지 추가조회
                return None
                
            if session.is_expired:  
                logger.info(f'[get_active_session] 세션이 만료됨: last_accessed_at = {session.last_accessed_at}')
                await self.delete_session(session_id)  
                return None
            
            # 세션 접근 시간 갱신
            session.touch()
            await self.db.commit()
            await self.db.refresh(session)
            
            #logger.info(f'[get_active_session] 유효한 세션 반환: {session}')
            return session
            
        except Exception as e:
            logger.error(f'[get_active_session] 오류 발생: {str(e)}', exc_info=True)
            return None

    async def update_session(
        self,
        session_id: str,
        session_in: SessionUpdate
    ) -> Optional[Session]:
        """세션 업데이트"""
        session = await self.get_session(session_id)
        if not session:
            return None

        update_data = session_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)

        session.touch()  # 접근 시간 갱신
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        session = await self.get_session(session_id)
        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()
        return True

    async def cleanup_expired_sessions(self) -> int:
        """만료된 세션 정리"""
        expiry_date = datetime.utcnow() - timedelta(days=settings.SESSION_EXPIRY_DAYS)
        logger.info(f'[cleanup_expired_sessions] Cleaning up sessions older than: {expiry_date}')
        result = await self.db.execute(
            select(Session).where(Session.last_accessed_at < expiry_date)
        )
        expired_sessions = result.scalars().all()
        
        logger.info(f'[cleanup_expired_sessions] Found {len(expired_sessions)} expired sessions')
        for session in expired_sessions:
            logger.info(f'[cleanup_expired_sessions] Deleting session: {session}')
            await self.db.delete(session)
        
        await self.db.commit()
        return len(expired_sessions)
