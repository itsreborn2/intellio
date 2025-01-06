"""카테고리 관련 API 라우터"""

from fastapi import APIRouter, Depends, Response, HTTPException
from fastapi.exceptions import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.schemas.category import CategoryResponse, CategoryCreate, AddProjectToCategory
from app.schemas.project import ProjectResponse
from app.models.category import Category
from app.models.project import Project
from app.models.user import Session
from app.core.deps import get_db, get_current_session
from uuid import UUID
import logging
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db)
):
    
    """사용자의 모든 카테고리를 조회합니다."""
    try:
        logger.info(f"사용자의 모든 카테고리를 조회합니다.")
        
        # 카테고리 조회
        stmt = select(Category)
        result = await db.execute(stmt)
        user_categories = result.scalars().all()
        return user_categories
    except HTTPException as he:
        # HTTP 예외는 그대로 전달 (401, 403 등)
        raise he
    except Exception as e:
        # 그 외 예외만 500으로 처리
        logger.error(f"카테고리 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=CategoryResponse)
async def create_category(
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """새로운 카테고리(영구 폴더)를 생성합니다."""
    try:
        # 동일한 이름의 카테고리(영구 폴더)가 있는지 확인
        stmt = select(Category).where(Category.name == category_in.name)
        result = await db.execute(stmt)
        existing_category = result.scalar_one_or_none()
        
        if existing_category:
            raise HTTPException(
                status_code=400,
                detail="Category with this name already exists"
            )
        
        # 새 카테고리 (영구 폴더)생성
        new_category = Category(
            name=category_in.name,
            type=category_in.type or "PERMANENT"  # 기본값 설정
        )
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        
        return new_category
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"=== 카테고리 삭제 시작 ===")
    logger.info(f"카테고리 ID (문자열): {category_id}")
    
    try:
        # 문자열을 UUID로 변환
        try:
            category_uuid = UUID(category_id)
            print(f"UUID 변환 성공: {category_uuid}")
        except ValueError as ve:
            print(f"UUID 변환 실패: {str(ve)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid category ID format"
            )

        # 1. 카테고리 존재 확인
        category = await db.get(Category, category_uuid)
        logger.info(f"조회된 카테고리: {category}")
        
        if not category:
            logger.debug(f"카테고리를 찾을 수 없음: {category_uuid}")
            raise HTTPException(
                status_code=404,
                detail="Category not found"
            )

        # 2. 프로젝트 연결 해제
        logger.info("프로젝트 연결 해제 시작")
        update_stmt = (
            update(Project)
            .where(Project.category_id == category_uuid)
            .values(category_id=None)
        )
        result = await db.execute(update_stmt)
        logger.info(f"프로젝트 연결 해제 완료: {result.rowcount}개")
        
        # 3. 카테고리 삭제
        logger.info("카테고리 삭제 시작")
        await db.delete(category)
        await db.commit()
        logger.info(f"카테고리 삭제 완료: {category_uuid}")
        
        # 성공 응답 반환
        logger.info("성공 응답 반환")
        return {"message": "Category deleted successfully"}
        
    except HTTPException as he:
        # HTTP 예외는 그대로 전달
        raise he
    except Exception as e:
        logger.info(f"=== 에러 발생 ===")
        logger.info(f"에러 타입: {type(e)}")
        logger.info(f"에러 메시지: {str(e)}")
        logger.info(f"=== 에러 상세 ===")
        import traceback
        logger.info(traceback.format_exc())
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete category: {str(e)}"
        )

@router.post("/{category_id}/projects", response_model=ProjectResponse)
async def add_project_to_category(
    category_id: str,
    project_data: AddProjectToCategory,
    db: AsyncSession = Depends(get_db)
):
    """카테고리(영구 폴더)에 프로젝트를 추가합니다."""
    try:
        logger.info(f"카테고리 {category_id}에 프로젝트 추가 시도")
        logger.info(f"요청 데이터: {project_data}")
        
        # 카테고리 존재 여부 확인
        stmt = select(Category).where(Category.id == category_id)
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()
        
        if not category:
            logger.error(f"카테고리를 찾을 수 없음: {category_id}")
            raise HTTPException(
                status_code=404,
                detail="Category not found"
            )

        # 프로젝트 존재 여부 확인
        stmt = select(Project).where(Project.id == project_data.project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()

        if not project:
            logger.error(f"프로젝트를 찾을 수 없음: {project_data.project_id}")
            raise HTTPException(
                status_code=404,
                detail="Project not found"
            )

        # 프로젝트의 카테고리 업데이트
        stmt = update(Project).where(Project.id == project_data.project_id).values(
            category_id=category_id,
            is_temporary=False  # 영구 프로젝트로 변경
        )
        await db.execute(stmt)
        await db.commit()

        # 업데이트된 프로젝트 조회
        stmt = select(Project).where(Project.id == project_data.project_id)
        result = await db.execute(stmt)
        updated_project = result.scalar_one()

        logger.info(f"프로젝트 {project_data.project_id}를 카테고리 {category_id}에 추가 완료")
        return updated_project

    except Exception as e:
        logger.error(f"프로젝트를 카테고리에 추가하는 중 오류 발생: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to add project to category"
        )

@router.get("/{category_id}/projects", response_model=List[ProjectResponse])
async def get_category_projects(
    category_id: str,
    db: AsyncSession = Depends(get_db)
):
    """카테고리에 속한 프로젝트 목록을 조회합니다."""
    # 카테고리 존재 여부 확인
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # 카테고리에 속한 프로젝트 조회
    stmt = select(Project).where(Project.category_id == category_id)
    result = await db.execute(stmt)
    projects = result.scalars().all()

    return [ProjectResponse(
        id=str(project.id),
        name=project.name,
        title=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at or project.created_at,
        is_temporary=project.is_temporary,
        category_id=category_id
    ) for project in projects]
