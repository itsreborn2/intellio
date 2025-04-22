from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime, timedelta

from common.services.user import UserService
from doceasy.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectSimpleResponse,
    ProjectListResponse,
    RecentProjectsResponse
)
from common.models.user import Session
from common.core.deps import get_current_session
from common.core.database import get_db_async
from doceasy.core.deps import get_project_service
from doceasy.models.project import Project
from doceasy.models.category import Category
from doceasy.services.project import ProjectService
from doceasy.models.document import Document
from doceasy.models.table_history import TableHistory

router = APIRouter() # 상위에서 등록 prefix="/projects", tags=["projects"]

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
    limit: Optional[int] = None,
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """최근 프로젝트 목록 조회"""
    try:
        logger.warning(f"최근 프로젝트 조회 시작 - Session: {session}")
        
        # 세션이 없거나 user_id가 없는 경우 빈 결과 반환
        if not session or not session.user_id:
            logger.warning("인증되지 않은 사용자의 접근")
            return RecentProjectsResponse(
                today=[],
                yesterday=[],
                four_days_ago=[],
                older=[]
            )

        # 사용자 ID로 최근 프로젝트 조회
        result = await project_service.get_recent_by_user_id(session.user_id, limit)
        logger.debug(f"프로젝트 조회 결과: {result}")
        return result

    except Exception as e:
        logger.error(f"최근 프로젝트 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프로젝트 목록을 조회하는 중 오류가 발생했습니다."
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
        logger.info(f"프로젝트 목록 조회 시도 - user ID: {session.user_id}")
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
    session: Session = Depends(get_current_session),
    project_service: ProjectService = Depends(get_project_service)
):
    """프로젝트 수정"""
    logger.info(f"프로젝트 업데이트 시도: {project_id}")
    logger.info(f"업데이트 데이터: {project_in}")
    try:
        project = await project_service.update(project_id, project_in, user_id=session.user_id)
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
    db: AsyncSession = Depends(get_db_async)
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

@router.delete("/{project_id}/delete_column")
async def delete_column(
    project_id: UUID,
    column_data: dict = Body(...),
    db: AsyncSession = Depends(get_db_async),
    session: Session = Depends(get_current_session)
):
    """
    프로젝트의 특정 컬럼 삭제
    
    column_data:
        - column_name: 삭제할 컬럼 이름
    """
    try:
        # 요청 데이터 검증
        column_name = column_data.get("column_name")
        if not column_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="컬럼 이름이 필요합니다."
            )
        
        logger.info(f"컬럼 삭제 시도: 프로젝트 {project_id}, 컬럼 {column_name}")
        # 사용자 활동 시간 업데이트
        user_service = UserService(db)
        await user_service.update_user_last_activity(session.user_id)

        # 1. 프로젝트 존재 확인
        stmt = select(Project).where(Project.id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            logger.warning(f"프로젝트를 찾을 수 없음: {project_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="프로젝트를 찾을 수 없습니다."
            )
        
        # 2. 프로젝트 소유자 확인
        if str(project.user_id) != str(session.user_id):
            logger.warning(f"권한 없음: 사용자 {session.user_id}가 프로젝트 {project_id}의 컬럼을 삭제할 수 없습니다.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 프로젝트의 컬럼을 삭제할 권한이 없습니다."
            )
        
        # 3. 프로젝트의 모든 문서 조회
        stmt = select(Document).where(Document.project_id == project_id)
        result = await db.execute(stmt)
        documents = result.scalars().all()
        
        # 5. table_histories 테이블에서 해당 컬럼 제목과 일치하는 레코드 삭제
        delete_stmt = delete(TableHistory).where(
            (TableHistory.project_id == project_id) & 
            (TableHistory.title == column_name)
        )
        result = await db.execute(delete_stmt)
        table_history_deleted_count = result.rowcount
        logger.info(f"table_histories 테이블에서 {table_history_deleted_count}개 레코드 삭제됨")
        
        # 6. 변경사항 저장
        await db.commit()
        
        logger.info(f"컬럼 삭제 완료: 프로젝트 {project_id}, 컬럼 {column_name}, {table_history_deleted_count}개 문서에서 삭제됨")
        return {
            "success": True,
            "message": f"컬럼 '{column_name}'이(가) 성공적으로 삭제되었습니다.",
            "deleted_count": table_history_deleted_count,
            "table_history_deleted_count": table_history_deleted_count
        }
        
    except HTTPException:
        # HTTP 예외는 그대로 전달
        raise
    except Exception as e:
        logger.error(f"컬럼 삭제 중 오류 발생: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"컬럼 삭제 중 오류가 발생했습니다: {str(e)}"
        )
