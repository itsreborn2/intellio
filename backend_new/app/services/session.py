from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Session

class SessionService:
    """세션 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: str) -> Optional[Session]:
        """세션 ID로 세션 조회"""
        result = await self.db.execute(
            select(Session).where(Session.session_id == session_id)
        )
        return result.scalars().first()

    async def create(self, session_id: str, user_id: Optional[UUID] = None) -> Session:
        """새 세션 생성"""
        session = Session(
            session_id=session_id,
            user_id=user_id,
            is_anonymous=user_id is None
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def update_last_accessed(self, session: Session) -> Session:
        """세션 마지막 접근 시간 업데이트"""
        session.update_last_accessed()
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete(self, session: Session) -> None:
        """세션 삭제"""
        await self.db.delete(session)
        await self.db.commit()
