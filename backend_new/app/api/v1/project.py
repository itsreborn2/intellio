from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime, timedelta

from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    RecentProjectsResponse
)
from app.models.user import Session
from app.models.project import Project
from app.models.category import Category
from app.core.deps import get_db, get_current_session, get_project_service, get_user_service
from app.services.project import ProjectService
from app.services.user import UserService
import sys
router = APIRouter()

logger = logging.getLogger(__name__)
#logger = logging.getLogger("app.api.v1.project")
logger.setLevel(logging.DEBUG)

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_in: ProjectCreate,
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """새 프로젝트 생성"""
    logger.info("=== 프로젝트 생성 API 호출 시작 ===")
    logger.info(f"입력 데이터: {project_in}")
    try:
        project = await project_service.create(project_in, session)
        logger.info(f"프로젝트 생성 성공 - ID: {project.id}")
        return project
    except Exception as e:
        logger.error(f"프로젝트 생성 실패: {str(e)}", exc_info=True)
        raise

@router.get("/recent", response_model=RecentProjectsResponse)
async def get_recent_projects(
    limit: int = 5,
    response: Response = None,
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """최근 프로젝트 목록 조회"""
    logger.debug(f"최근 프로젝트 조회 - 세션 ID: {session.session_id}")
    
    try:
        # 최근 프로젝트 조회
        projects = await project_service.get_recent(session=session, limit=limit)
        return {"projects": projects}
        
    except Exception as e:
        logger.error(f"최근 프로젝트 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="최근 프로젝트 조회 중 오류가 발생했습니다."
        )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 조회"""
    logger.info(f"프로젝트 조회 시도: {project_id}")
    try:
        project = await project_service.get(project_id)
        if not project:
            logger.warning(f"프로젝트를 찾을 수 없음: {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="프로젝트를 찾을 수 없습니다."
            )
        logger.info(f"프로젝트 조회 결과: {project}")
        return project
    except Exception as e:
        logger.error(f"프로젝트 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise

@router.get("/{project_id}/metadata")
async def get_project_metadata(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 메타데이터만 조회"""
    metadata = await project_service.get_metadata(project_id)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    return metadata

@router.get("/{project_id}/content/{doc_id}")
async def get_document_content(
    project_id: UUID,
    doc_id: UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    """특정 문서의 내용만 조회"""
    content = await project_service.get_document_content(project_id, doc_id)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문서를 찾을 수 없습니다."
        )
    return content

@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 10,
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 목록 조회"""
    total, items = await project_service.get_multi(
        skip=skip,
        limit=limit,
        session=session
    )
    return {
        "total": total,
        "items": items,
        "skip": skip,
        "limit": limit
    }

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 수정"""
    logger.info(f"프로젝트 업데이트 시도: {project_id}")
    logger.info(f"업데이트 데이터: {project_in}")
    try:
        project = await project_service.update(project_id, project_in)
        if not project:
            logger.warning(f"프로젝트를 찾을 수 없음: {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="프로젝트를 찾을 수 없습니다."
            )
        logger.info(f"프로젝트 업데이트 완료: {project_id}")
        return project
    except Exception as e:
        logger.error(f"프로젝트 업데이트 중 오류 발생: {str(e)}", exc_info=True)
        raise

@router.put("/{project_id}/autosave")
async def autosave_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 자동 저장"""
    try:
        project = await project_service.update(project_id, project_in)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="프로젝트를 찾을 수 없습니다."
            )
        return {"message": "자동 저장 완료"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"자동 저장 실패: {str(e)}"
        )

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_category(
    project_id: UUID,
    project_update: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """프로젝트 카테고리 업데이트"""
    try:
        # 프로젝트 조회
        stmt = select(Project).where(Project.id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail="Project not found"
            )
        
        # 카테고리 ID가 제공된 경우, 카테고리 존재 여부 확인
        if project_update.category_id:
            stmt = select(Category).where(Category.id == project_update.category_id)
            result = await db.execute(stmt)
            category = result.scalar_one_or_none()
            
            if not category:
                raise HTTPException(
                    status_code=404,
                    detail="Category not found"
                )
        
        # 프로젝트 업데이트
        for field, value in project_update.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        
        await db.commit()
        await db.refresh(project)
        
        return project
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 삭제"""
    logger.info(f"프로젝트 삭제 시도: {project_id}")
    try:
        success = await project_service.delete(project_id)
        if not success:
            logger.warning(f"프로젝트를 찾을 수 없음: {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="프로젝트를 찾을 수 없습니다."
            )
        logger.info(f"프로젝트 삭제 완료: {project_id}")
        return {"message": "프로젝트가 삭제되었습니다."}
    except Exception as e:
        logger.error(f"프로젝트 삭제 중 오류 발생: {str(e)}", exc_info=True)
        raise
