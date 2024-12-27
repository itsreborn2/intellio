from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.core.deps import get_db, get_current_session, get_project_service
from app.services.project import ProjectService

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_in: ProjectCreate,
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """새 프로젝트 생성"""
    return await project_service.create(project_in, session)

@router.get("/recent", response_model=RecentProjectsResponse)
async def get_recent_projects(
    limit: int = 5,
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """최근 프로젝트 목록 조회"""
    result = await project_service.get_recent(
        limit=limit,
        session=session
    )
    return {
        "today": result["today"],
        "yesterday": result["yesterday"],
        "four_days_ago": result["four_days_ago"]
    }

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 조회"""
    project = await project_service.get(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    return project

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
    project = await project_service.update(project_id, project_in)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    return project

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
    success = await project_service.delete(project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="프로젝트를 찾을 수 없습니다."
        )
    return {"message": "프로젝트가 삭제되었습니다."}
