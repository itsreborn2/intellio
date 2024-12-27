"""카테고리 관련 API 라우터"""

from fastapi import APIRouter, Depends, Response
from fastapi.exceptions import HTTPException
from typing import List
from app.schemas.category import CategoryResponse, CategoryCreate
from app.core.deps import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.category import Category
from app.models.project import Project

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """사용자의 모든 카테고리를 조회합니다."""
    try:
        # 카테고리 조회
        stmt = select(Category)
        result = await db.execute(stmt)
        user_categories = result.scalars().all()
        return user_categories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=CategoryResponse)
async def create_category(
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """새로운 카테고리를 생성합니다."""
    try:
        # 동일한 이름의 카테고리가 있는지 확인
        stmt = select(Category).where(Category.name == category_in.name)
        result = await db.execute(stmt)
        existing_category = result.scalar_one_or_none()
        
        if existing_category:
            raise HTTPException(
                status_code=400,
                detail="Category with this name already exists"
            )
        
        # 새 카테고리 생성
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

@router.delete("/{category_id}", response_model=None)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db)
):
    """카테고리를 삭제합니다."""
    try:
        # 카테고리 조회
        stmt = select(Category).where(Category.id == category_id)
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()
        
        if not category:
            raise HTTPException(
                status_code=404,
                detail="Category not found"
            )
        
        # 카테고리에 속한 프로젝트들의 category_id를 null로 설정
        update_stmt = (
            update(Project)
            .where(Project.category_id == category_id)
            .values(category_id=None)
        )
        await db.execute(update_stmt)
        
        # 카테고리 삭제
        await db.delete(category)
        await db.commit()
        
        return Response(status_code=204)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
