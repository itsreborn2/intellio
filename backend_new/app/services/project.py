from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import Session
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectInDB
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
        # 사용자 이메일을 로그에 기록
        user_email = session.user.email if session.user else 'Unknown'
        #print(f"프로젝트 생성 - 사용자 이메일: {user_email}")
        logger.info(f"프로젝트 생성 - 사용자 이메일: {user_email}, 세션: {session.session_id}")
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
    ) -> List[Project]:
        """프로젝트 목록 조회"""
        try:
            query = select(Project)
            
            if session:
                # 세션 ID로 필터링
                query = query.where(Project.session_id == session.session_id)
                
                # 사용자 ID로도 필터링 (옵션)
                if session.user_id:
                    query = query.where(Project.user_id == session.user_id)
            
            # 정렬 및 페이지네이션 적용
            query = query.order_by(Project.created_at.desc())
            query = query.offset(skip).limit(limit)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"프로젝트 목록 조회 중 오류 발생: {str(e)}")
            raise

    async def get_recent(
        self,
        session: Optional[Session] = None,
        limit: int = 5
    ) -> Dict[str, List[Project]]:
        """최근 프로젝트 목록 조회"""
        # 현재 시간 기준으로 날짜 범위 계산
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        this_week_start = today_start - timedelta(days=today_start.weekday())
        this_month_start = today_start.replace(day=1)

        # 기본 쿼리
        base_query = select(Project)
        if session:
            base_query = base_query.where(Project.session_id == session.session_id)

        # 각 기간별 프로젝트 조회
        async def get_projects_for_period(start_time, end_time=None):
            query = base_query.where(Project.created_at >= start_time)
            if end_time:
                query = query.where(Project.created_at < end_time)
            query = query.order_by(Project.created_at.desc()).limit(limit)
            result = await self.db.execute(query)
            return list(result.scalars().all())

        # 각 기간별 프로젝트 조회 실행
        today = await get_projects_for_period(today_start)
        yesterday = await get_projects_for_period(yesterday_start, today_start)
        this_week = await get_projects_for_period(this_week_start, yesterday_start)
        this_month = await get_projects_for_period(this_month_start, this_week_start)
        older = await get_projects_for_period(datetime.min, this_month_start)

        return {
            "today": today,
            "yesterday": yesterday,
            "this_week": this_week,
            "this_month": this_month,
            "older": older
        }

    async def get_recent_by_user_id(
        self,
        user_id: UUID,
        limit: int = 5
    ) -> List[Project]:
        """사용자 ID로 최근 프로젝트 목록 조회"""
        query = (
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc())
            .limit(limit)
        )
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
