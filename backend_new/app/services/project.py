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
        logger.info(f"get_recent - 세션: {session.session_id}")
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        yesterday_start = today_start - timedelta(days=1)
        four_days_ago_start = today_start - timedelta(days=4)
        four_days_ago_end = today_start - timedelta(days=3)

        # 기본 쿼리 생성
        base_query = select(Project)
        #base_query = select(Project).where(Project.is_temporary == True)
        if session:
            if session.user_id:
                base_query = base_query.where(Project.user_id == session.user_id)
            else:
                base_query = base_query.where(Project.session_id == session.session_id)

        # 오늘 생성된 프로젝트
        today_query = base_query.where(
            Project.created_at >= today_start
        ).order_by(Project.created_at.desc()).limit(limit)
        
        # 어제 생성된 프로젝트
        yesterday_query = base_query.where(
            Project.created_at >= yesterday_start,
            Project.created_at < today_start
        ).order_by(Project.created_at.desc()).limit(limit)
        
        # 4일 전 생성된 프로젝트
        four_days_ago_query = base_query.where(
            Project.created_at >= four_days_ago_start,
            Project.created_at < four_days_ago_end
        ).order_by(Project.created_at.desc()).limit(limit)

        # 각 쿼리 실행
        today_result = await self.db.execute(today_query)
        yesterday_result = await self.db.execute(yesterday_query)
        four_days_ago_result = await self.db.execute(four_days_ago_query)

        # 결과 반환
        return {
            "today": list(today_result.scalars().all()),
            "yesterday": list(yesterday_result.scalars().all()),
            "four_days_ago": list(four_days_ago_result.scalars().all())
        }

    async def get_recent_by_user_id(
        self,
        user_id: UUID,
        limit: int = 5
    ) -> Dict[str, List[Project]]:
        """사용자 ID로 최근 프로젝트 목록 조회"""
        # 현재 시간 기준으로 날짜 범위 계산
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        yesterday_start = today_start - timedelta(days=1)
        four_days_ago_start = today_start - timedelta(days=4)

        # 기본 쿼리 생성
        base_query = select(Project).where(Project.user_id == user_id)

        # 오늘 생성된 프로젝트
        today_query = base_query.where(
            Project.created_at >= today_start
        ).order_by(Project.created_at.desc()).limit(limit)
        
        # 어제 생성된 프로젝트
        yesterday_query = base_query.where(
            Project.created_at >= yesterday_start,
            Project.created_at < today_start
        ).order_by(Project.created_at.desc()).limit(limit)
        
        # 4일 전 이전에 생성된 프로젝트
        older_query = base_query.where(
            Project.created_at < four_days_ago_start
        ).order_by(Project.created_at.desc()).limit(limit)

        # 각 쿼리 실행
        today_result = await self.db.execute(today_query)
        yesterday_result = await self.db.execute(yesterday_query)
        older_result = await self.db.execute(older_query)

        # 결과 반환
        return {
            "today": list(today_result.scalars().all()),
            "yesterday": list(yesterday_result.scalars().all()),
            "four_days_ago": [],  # 4일 전 프로젝트는 older로 통합
            "older": list(older_result.scalars().all())
        }

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
