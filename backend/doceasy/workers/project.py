from app.core.celery_app import celery
from app.core.database import SessionLocal
from app.services.project import ProjectService
import logging

logger = logging.getLogger(__name__)

@celery.task(name="app.workers.project.cleanup_expired_projects")
async def cleanup_expired_projects():
    """만료된 임시 프로젝트 정리 작업 (마지막 수정일로부터 30일 경과된 임시 프로젝트 삭제)"""
    async with SessionLocal() as db:
        try:
            project_service = ProjectService(db)
            await project_service.cleanup_expired_projects()
        except Exception as e:
            logger.error(f"프로젝트 정리 중 오류 발생: {str(e)}")
            raise

@celery.task(name="app.workers.project.update_retention_periods")
async def update_retention_periods():
    """프로젝트 보관 기간 업데이트 작업"""
    async with SessionLocal() as db:
        try:
            project_service = ProjectService(db)
            await project_service.update_retention_periods()
        except Exception as e:
            logger.error(f"보관 기간 업데이트 중 오류 발생: {str(e)}")
            raise
