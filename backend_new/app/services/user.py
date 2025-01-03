from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from uuid import UUID, uuid4
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash, verify_password
from app.models.user import User, Session
from app.schemas.user import UserCreate, UserUpdate, UserLogin, SessionCreate, SessionUpdate
from app.core.config import settings

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
        db_user = User(
            id=uuid4(),  # UUID 자동 생성
            email=user_data["email"],
            name=user_data["name"],
            oauth_provider=user_data["oauth_provider"],
            oauth_provider_id=user_data["oauth_provider_id"],
            is_active=True,
            is_superuser=False
        )
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def create_session(self, session_in: SessionCreate) -> Session:
        """새 세션 생성"""
        db_session = Session(
            id=uuid4(),
            session_id=session_in.session_id,
            user_id=session_in.user_id,
            is_anonymous=session_in.is_anonymous
        )
        self.db.add(db_session)
        await self.db.commit()
        await self.db.refresh(db_session)
        return db_session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """세션 조회"""
        result = await self.db.execute(
            select(Session)
            .options(selectinload(Session.user))
            .where(Session.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_active_session(self, session_id: str) -> Optional[Session]:
        """활성 세션 조회"""
        session = await self.get_session(session_id)
        if not session or session.is_expired:
            return None
        return session

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
        result = await self.db.execute(
            select(Session).where(Session.last_accessed_at < expiry_date)
        )
        expired_sessions = result.scalars().all()
        
        for session in expired_sessions:
            await self.db.delete(session)
        
        await self.db.commit()
        return len(expired_sessions)
