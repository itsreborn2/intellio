"""카테고리 관련 API 라우터"""

from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from common.services.embedding import EmbeddingService
from common.services.vector_store_manager import VectorStoreManager
from doceasy.models.document import Document
from doceasy.services.document import DocumentService
from doceasy.schemas.category import CategoryResponse, CategoryCreate, AddProjectToCategory
from doceasy.schemas.project import ProjectSimpleResponse
from doceasy.models.category import Category
from doceasy.models.project import Project
from doceasy.models.table_history import TableHistory
from common.models.user import Session
from common.core.deps import get_current_session, get_embedding_service, get_vector_manager
from common.core.database import  get_db_async
from uuid import UUID
#import logging
from fastapi.responses import JSONResponse

#logger = logging.getLogger(__name__)
from loguru import logger

router = APIRouter()

logger.info("카테고리 라우터 초기화")

@router.get("", response_model=List[CategoryResponse])
async def get_categories(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """사용자의 모든 카테고리를 조회합니다."""
    try:
        logger.info(f"GET /categories 요청 받음 - User ID: {session.user_id}")

        # 익명 사용자 체크
        if session.is_anonymous or not session.user_id:
            logger.warning("익명 사용자는 카테고리를 조회할 수 없습니다.")
            raise HTTPException(
                status_code=403,
                detail="로그인이 필요한 기능입니다."
            )
            
        logger.info(f"사용자 {session.user_id}의 모든 카테고리를 조회합니다.")
        
        # 사용자의 카테고리만 조회
        query = select(Category).where(Category.user_id == session.user_id)
        logger.debug(f"실행할 쿼리: {query}")
        
        result = await db.execute(query)
        categories = result.scalars().all()
        
        # 카테고리가 없는 경우 빈 리스트 반환
        if not categories:
            logger.info(f"사용자 {session.user_id}의 카테고리가 없습니다.")
            return []
            
        logger.info(f"사용자 {session.user_id}의 카테고리 {len(categories)}개를 조회했습니다.")
        return categories
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카테고리 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="카테고리 조회 중 오류가 발생했습니다."
        )

@router.post("", response_model=CategoryResponse)
async def create_category(
    category_in: CategoryCreate,
    session: Session = Depends(get_current_session), 
    db: AsyncSession = Depends(get_db_async)
):
    logger.error(f"Create 프로젝트 폴더")
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
            user_id=session.user_id,
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
    db: AsyncSession = Depends(get_db_async)
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

@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    category_data: CategoryCreate,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """카테고리 정보를 업데이트합니다."""
    logger.info(f"PUT /categories/{category_id} 요청 받음 - User ID: {session.user_id}")
    
    try:
        # 카테고리 존재 여부 확인
        query = select(Category).where(Category.id == category_id)
        result = await db.execute(query)
        category = result.scalar_one_or_none()
        
        if not category:
            logger.warning(f"카테고리를 찾을 수 없음: {category_id}")
            raise HTTPException(
                status_code=404,
                detail="카테고리를 찾을 수 없습니다."
            )
            
        # 권한 확인
        if category.user_id != session.user_id:
            logger.warning(f"카테고리 수정 권한 없음: {category_id}")
            raise HTTPException(
                status_code=403,
                detail="이 카테고리를 수정할 권한이 없습니다."
            )
            
        # 동일한 이름의 다른 카테고리가 있는지 확인
        name_check = select(Category).where(
            Category.name == category_data.name,
            Category.id != category_id,
            Category.user_id == session.user_id
        )
        existing = await db.execute(name_check)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="같은 이름의 카테고리가 이미 존재합니다."
            )
            
        # 카테고리 업데이트
        category.name = category_data.name
        await db.commit()
        await db.refresh(category)
        
        logger.info(f"카테고리 업데이트 성공: {category_id}")
        return category
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카테고리 업데이트 중 오류 발생: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="카테고리 업데이트 중 오류가 발생했습니다."
        )

@router.post("/{category_id}/projects", response_model=ProjectSimpleResponse)
async def add_project_to_category(
    category_id: str,
    project_data: AddProjectToCategory,
    db: AsyncSession = Depends(get_db_async)
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

@router.get("/{category_id}/projects", response_model=List[ProjectSimpleResponse])
async def get_category_projects(
    category_id: str,
    db: AsyncSession = Depends(get_db_async)
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

    return [ProjectSimpleResponse(
        id=str(project.id),
        name=project.name,
        title=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at or project.created_at,
        is_temporary=project.is_temporary,
        category_id=category_id
    ) for project in projects]

@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db_async),
    current_user: Session = Depends(get_current_session),
    vs:VectorStoreManager = Depends(get_vector_manager)
):
    """
    프로젝트와 관련된 모든 데이터를 삭제합니다.
    
    Args:
        project_id (str): 삭제할 프로젝트의 ID
        db (AsyncSession): 데이터베이스 세션
        current_user (Session): 현재 로그인한 사용자
    
    Returns:
        JSONResponse: 삭제 성공 메시지
        
    Raises:
        HTTPException: 프로젝트가 존재하지 않거나 권한이 없는 경우
    """
    try:
        # 프로젝트 존재 여부 및 권한 확인
        logger.info(f"프로젝트 삭제 시작: {project_id}")
        query = select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.user_id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail="프로젝트를 찾을 수 없거나 접근 권한이 없습니다."
            )
        
        # Pinecone 임베딩 삭제
        # 프로젝트와 연관된 모든 문서의 임베딩 ID 조회
        query = select(Document.embedding_ids).where(
            Document.project_id == project_id,
        )
        result = await db.execute(query)
        ids = result.scalars().all()
        logger.info(f"삭제할 문서 : {len(ids)}개")
        
        import json
        remove_list = []
        for id in ids:
            if id:  # None 체크
                chunk_ids = json.loads(id)
                remove_list.extend(chunk_ids)
        
        logger.info(f"삭제할 문서 : {len(ids)}개, 임베딩 ID : {len(remove_list)}개")

        #vs.delete_documents_by_embedding_id(remove_list)
        await vs.delete_documents_by_embedding_id_async(remove_list)

        # 프로젝트와 연관된 모든 데이터 삭제
        # 1. 문서 및 문서 청크 삭제
        # (Document 모델의 cascade="all, delete-orphan" 설정으로 인해 
        # 프로젝트 삭제 시 자동으로 관련 문서와 청크가 삭제됩니다)
        
        # 2. 테이블 검색 기록 삭제
        await db.execute(
            delete(TableHistory).where(TableHistory.project_id == project_id)
        )
        
        # 3. 프로젝트 삭제
        # (프로젝트 삭제 시 cascade 설정에 의해 관련 문서들도 자동 삭제됨)
        await db.delete(project)
        
        # 변경사항 커밋
        await db.commit()


        logger.info(f"프로젝트 삭제 완료: {project_id}")
        return {"message": "프로젝트가 성공적으로 삭제되었습니다."}
        
    except Exception as e:
        await db.rollback()
        logger.exception(f"프로젝트 삭제 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"프로젝트 삭제 중 오류가 발생했습니다: {str(e)}"
        )
