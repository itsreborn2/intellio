from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict
from uuid import UUID
from sqlalchemy import select, func, and_
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
            #session_id=session.session_id
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        # 사용자 이메일을 로그에 기록
        user_email = session.user.email if session.user else 'Unknown'
        #print(f"프로젝트 생성 - 사용자 이메일: {user_email}")
        logger.info(f"프로젝트 생성 - 사용자 이메일: {user_email}, 사용자ID: {session.user_id}")
        return project

    async def get(self, project_id: UUID, user_id:UUID) -> Optional[Project]:
        """프로젝트 조회"""

        #프로젝트의 조회를 세션말고
        if user_id:
            # SQLAlchemy의 and_ 함수를 사용하여 여러 조건을 결합
            query = select(Project).where(and_(Project.user_id == user_id, Project.id == project_id))
        else:
            query = select(Project).where(Project.id == project_id)
        
        result = await self.db.execute(query)
        project_row = result.first()
        
        if project_row:
            project = project_row[0] # result.first()는 튜플을 반환하므로 인덱싱 필요
            # 프로젝트 조회 시 마지막 접근 시간 갱신
            project.updated_at = datetime.utcnow()
            await self.db.commit()
            logger.debug(f"프로젝트 {project_id} 마지막 접근 시간 갱신: {project.updated_at}")
            return project
        else:
            logger.warning("프로젝트를 찾을 수 없습니다.")
            return None
        

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
                # 세션 ID를 이용한 각종 조회작업은 하지 않음.
                #query = query.where(Project.user_id == session.user_id)
                
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
    ) -> Dict[str, List[Project]]:
        """최근 프로젝트 목록 조회
        
        Returns:
            Dict[str, List[Project]]: 다음 기간별 프로젝트 목록
            - today: 오늘 생성/수정된 프로젝트
            - last_7_days: 지난 7일간 생성/수정된 프로젝트
            - last_30_days: 지난 30일간 생성/수정된 프로젝트
        """
        logger.info(f"get_recent - UserID: {session.user_id}")
        # KST (UTC+9) 시간대 설정
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        today_start = datetime(now.year, now.month, now.day, tzinfo=kst)
        last_7_days_start = today_start - timedelta(days=7)
        last_30_days_start = today_start - timedelta(days=30)

        # UTC로 변환
        today_start_utc = today_start.astimezone(timezone.utc)
        last_7_days_start_utc = last_7_days_start.astimezone(timezone.utc)
        last_30_days_start_utc = last_30_days_start.astimezone(timezone.utc)

        # 기본 쿼리 생성
        base_query = select(Project)
        if session and session.user_id:
            base_query = base_query.where(Project.user_id == session.user_id)
        else:
            return {
                "today": [],
                "last_7_days": [],
                "last_30_days": []
            }

        # 오늘 생성/수정된 프로젝트
        today_query = base_query.where(
            Project.updated_at >= today_start_utc
        ).order_by(Project.updated_at.desc())
        
        # 지난 7일간 생성/수정된 프로젝트 (오늘 제외)
        last_7_days_query = base_query.where(
            Project.updated_at >= last_7_days_start_utc,
            Project.updated_at < today_start_utc
        ).order_by(Project.updated_at.desc())
        
        # 지난 30일간 생성/수정된 프로젝트 (지난 7일 제외)
        last_30_days_query = base_query.where(
            Project.updated_at >= last_30_days_start_utc,
            Project.updated_at < last_7_days_start_utc
        ).order_by(Project.updated_at.desc())

        # 각 쿼리 실행
        today_result = await self.db.execute(today_query)
        last_7_days_result = await self.db.execute(last_7_days_query)
        last_30_days_result = await self.db.execute(last_30_days_query)

        # 결과 반환
        return {
            "today": list(today_result.scalars().all()),
            "last_7_days": list(last_7_days_result.scalars().all()),
            "last_30_days": list(last_30_days_result.scalars().all())
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
        last_7_days_start = today_start - timedelta(days=7)
        last_30_days_start = today_start - timedelta(days=30)

        # 기본 쿼리 생성
        base_query = select(Project).where(Project.user_id == user_id)

        # 오늘 생성된 프로젝트
        today_query = base_query.where(
            Project.created_at >= today_start
        ).order_by(Project.created_at.desc()).limit(limit)
        
        # 7일 이내 생성된 프로젝트
        last_7_days_query = base_query.where(
            Project.created_at >= last_7_days_start,
            Project.created_at < today_start
        ).order_by(Project.created_at.desc()).limit(limit)
        
        # 30일 이내 생성된 프로젝트
        last_30_days_query = base_query.where(
            Project.created_at >= last_30_days_start,
            Project.created_at < last_7_days_start
        ).order_by(Project.created_at.desc()).limit(limit)

        # 각 쿼리 실행
        today_result = await self.db.execute(today_query)
        last_7_days_result = await self.db.execute(last_7_days_query)
        last_30_days_result = await self.db.execute(last_30_days_query)

        # 결과 반환
        return {
            "today": list(today_result.scalars().all()),
            "last_7_days": list(last_7_days_result.scalars().all()),
            "last_30_days": list(last_30_days_result.scalars().all())
        }

    async def update(
        self,
        project_id: UUID,
        project_in: ProjectUpdate,
        user_id: UUID
    ) -> Optional[Project]:
        """프로젝트 수정"""
        project = await self.get(project_id, user_id)
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

    async def cleanup_expired_projects(self) -> int:
        """30일 동안 수정되지 않은 임시 프로젝트 정리 작업"""
        try:
            # 30일 전 날짜 계산
            expiration_date = datetime.utcnow() - timedelta(days=30)
            
            # 만료된 임시 프로젝트 조회 (마지막 수정일 기준)
            query = select(Project).where(
                and_(
                    Project.is_temporary == True,
                    Project.updated_at < expiration_date
                )
            )
            
            result = await self.db.execute(query)
            expired_projects = result.scalars().all()
            
            # 만료된 프로젝트 삭제
            count = 0
            for project in expired_projects:
                await self.db.delete(project)
                count += 1
            
            await self.db.commit()
            logger.info(f"{count}개의 만료된 임시 프로젝트가 삭제되었습니다. (마지막 수정일로부터 30일 경과)")
            return count
            
        except Exception as e:
            logger.error(f"임시 프로젝트 정리 중 오류 발생: {str(e)}")
            raise
