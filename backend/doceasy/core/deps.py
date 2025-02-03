from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from common.core.deps import get_db_async
from doceasy.services.project import ProjectService
from doceasy.services.document import DocumentService
import logging

logger = logging.getLogger(__name__)


def get_project_service(
    db: AsyncSession = Depends(get_db_async)
) -> ProjectService:
    """프로젝트 서비스 의존성"""
    return ProjectService(db)

def get_document_service(
    db: AsyncSession = Depends(get_db_async)
) -> DocumentService:
    """문서 서비스 의존성"""
    return DocumentService(db)
