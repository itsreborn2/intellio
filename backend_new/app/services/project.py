from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import Session
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectInDB

class ProjectService:
    """프로젝트 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, project_in: ProjectCreate, session: Session) -> Project:
        """새 프로젝트 생성"""
        project = Project(
            **project_in.dict(),
            user_id=session.user_id,
            session_id=session.session_id
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get(self, project_id: UUID, session_id: Optional[str] = None) -> Optional[Project]:
        """프로젝트 조회"""
        query = select(Project).where(Project.id == project_id)
        
        if session_id:
            query = query.where(Project.session_id == session_id)
            
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 10,
        session: Optional[Session] = None
    ) -> Tuple[int, List[Project]]:
        """프로젝트 목록 조회"""
        query = select(Project)
        
        if session:
            if session.user_id:
                # 로그인된 사용자의 프로젝트
                query = query.where(Project.user_id == session.user_id)
            else:
                # 익명 세션의 프로젝트
                query = query.where(Project.session_id == session.session_id)
        
        # 전체 개수 조회
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # 페이지네이션 적용
        query = query.order_by(Project.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return total, list(items)

    async def get_recent(
        self,
        session: Session,
        limit: int = 5,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Project]:
        """최근 프로젝트 조회"""
        query = select(Project)
        
        if session.user_id:
            query = query.where(Project.user_id == session.user_id)
        else:
            query = query.where(Project.session_id == session.session_id)

        if start_date:
            query = query.where(Project.created_at >= start_date)
        
        if end_date:
            query = query.where(Project.created_at < end_date)

        query = query.order_by(Project.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        project_id: UUID,
        project_in: ProjectUpdate
    ) -> Optional[Project]:
        """프로젝트 수정"""
        project = await self.get(project_id)
        if not project:
            return None
        
        for field, value in project_in.dict(exclude_unset=True).items():
            setattr(project, field, value)
        
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete(self, project_id: UUID) -> bool:
        """프로젝트 삭제"""
        project = await self.get(project_id)
        if not project:
            return False
        
        await self.db.delete(project)
        await self.db.commit()
        return True
