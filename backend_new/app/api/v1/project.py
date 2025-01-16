from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime, timedelta
import pdb

from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectSimpleResponse,
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

@router.post("/", response_model=ProjectSimpleResponse)
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
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
    #user_service: UserService = Depends(get_user_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """최근 프로젝트 목록 조회"""
    logger.debug(f"최근 프로젝트 조회 - User Id:{session.user_id}, 세션 ID: {session.session_id}")
    
    try:
        logger.info(f"get_recent_projects : {session}")
        # 세션 검증
        if not session or not session.is_authenticated or not session.user:
            logger.warning("인증되지 않은 사용자의 접근")
            return RecentProjectsResponse(
                today=[],
                yesterday=[],
                four_days_ago=[],
                older=[]
            )

        # email = session.user.email
        # logger.info(f"최근 프로젝트 조회 - 사용자: {email}")

        # 이메일로 사용자 조회
        # user = await user_service.get_by_email(email)
        # if not user:
        #     logger.error(f"사용자를 찾을 수 없음: {email}")
        #     return RecentProjectsResponse(
        #         today=[],
        #         yesterday=[],
        #         four_days_ago=[],
        #         older=[]
        #     )

        # 사용자 ID로 최근 프로젝트 조회
        result = await project_service.get_recent_by_user_id(session.user_id, limit)
        return result

    except Exception as e:
        logger.error(f"최근 프로젝트 조회 중 오류 발생: {str(e)}", exc_info=True)
        return RecentProjectsResponse(
            today=[],
            yesterday=[],
            four_days_ago=[],
            older=[]
        )

@router.get("/{project_id}", response_model=ProjectSimpleResponse)
async def get_project_info(
    project_id: UUID,
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 조회"""
    logger.info(f"프로젝트 조회 시도: {project_id}, 세션의 userid : {session.user_id}")
    try:
        user_id = session.user.id
        project = await project_service.get(project_id, user_id)
        if not project:
            logger.warning(f"프로젝트를 찾을 수 없음: {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="프로젝트를 찾을 수 없습니다."
            )
        logger.info(f"프로젝트 조회 결과: {project.name}, {project.id}")

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
    try:
        logger.info(f"프로젝트 목록 조회 시도 - 세션 ID: {session.session_id}")
        projects = await project_service.get_multi(
            skip=skip,
            limit=limit,
            session=session
        )
        
        if not projects:
            # 프로젝트가 없는 경우 빈 리스트 반환
            return {"projects": []}
            
        return {"projects": projects}
        
    except Exception as e:
        logger.error(f"프로젝트 목록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프로젝트 목록 조회 중 오류가 발생했습니다."
        )

@router.put("/{project_id}", response_model=ProjectSimpleResponse)
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
    # 굳이 사용할 필요없음. 일단 주석으로만 블록처리.
    # logger.info(f"프로젝트 자동 저장 시도: {project_id}")
    # logger.info(f"자동 저장 데이터: {project_in}")
    # try:
    #     project = await project_service.update(project_id, project_in)
    #     if not project:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail="프로젝트를 찾을 수 없습니다."
    #         )
    #     return {"message": "자동 저장 완료"}
    # except Exception as e:
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail=f"자동 저장 실패: {str(e)}"
    #     )

@router.patch("/{project_id}", response_model=ProjectSimpleResponse)
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
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 삭제"""
    logger.info(f"프로젝트 삭제 시도: {project_id}")
    try:
        success = await project_service.delete(project_id, session.user_id)
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
