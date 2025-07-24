"""
관심기업(즐겨찾기) API 라우터.

PM 지시사항에 따른 새로운 관심기업(즐겨찾기) 기능을 위한 API 엔드포인트들
카테고리별 관리, 정렬순서, 메모 기능 포함
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from common.core.database import get_db_async
from common.core.deps import get_current_session
from common.models.user import Session
from stockeasy.services.stock_favorite_service import StockFavoriteService
from stockeasy.schemas.stock_favorites import (
    StockFavoriteCreate,
    StockFavoriteUpdate,
    StockFavoriteResponse,
    StockFavoriteToggleRequest,
    StockFavoriteToggleResponse,
    CategoryResponse,
    StockFavoritesByCategory
)

# 관심기업(즐겨찾기) API 라우터
stock_favorites_router = APIRouter(prefix="/stock-favorites", tags=["관심기업(즐겨찾기)"])


@stock_favorites_router.get(
    "/",
    response_model=List[StockFavoriteResponse],
    summary="관심기업(즐겨찾기) 목록 조회",
    description="현재 사용자의 관심기업(즐겨찾기) 종목 목록을 조회합니다. 카테고리별 필터링 가능합니다."
)
async def get_stock_favorites(
    category: Optional[str] = Query(None, description="카테고리명 (선택사항)"),
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """사용자의 관심기업(즐겨찾기) 목록을 조회합니다."""
    try:
        favorites = await StockFavoriteService.get_favorites_by_user_id(db, session.user_id, category)
        return [StockFavoriteResponse(
            id=favorite.id,
            user_id=favorite.user_id,
            stock_code=favorite.stock_code,
            stock_name=favorite.stock_name,
            category=favorite.category,
            display_order=favorite.display_order,
            memo=favorite.memo,
            created_at=favorite.created_at,
            updated_at=favorite.updated_at
        ) for favorite in favorites]
    except Exception as e:
        logger.error(f"관심기업 목록 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 목록을 조회하는 중 오류가 발생했습니다."
        )


@stock_favorites_router.get(
    "/by-category",
    response_model=List[StockFavoritesByCategory],
    summary="카테고리별 관심기업 목록 조회",
    description="사용자의 관심기업을 카테고리별로 그룹화하여 조회합니다."
)
async def get_favorites_by_category(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """카테고리별로 그룹화된 관심기업 목록을 조회합니다."""
    try:
        favorites_by_category = await StockFavoriteService.get_favorites_by_category(db, session.user_id)
        
        result = []
        for category, favorites in favorites_by_category.items():
            result.append(StockFavoritesByCategory(
                category=category,
                favorites=[StockFavoriteResponse.from_attributes(fav) for fav in favorites]
            ))
        
        return result
    except Exception as e:
        logger.error(f"카테고리별 관심기업 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리별 관심기업을 조회하는 중 오류가 발생했습니다."
        )


@stock_favorites_router.get(
    "/categories",
    response_model=List[CategoryResponse],
    summary="카테고리 목록 조회",
    description="사용자의 카테고리 목록과 각 카테고리별 종목 수를 조회합니다."
)
async def get_categories(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """사용자의 카테고리 목록을 조회합니다."""
    try:
        categories = await StockFavoriteService.get_categories_by_user_id(db, session.user_id)
        return [CategoryResponse(**category) for category in categories]
    except Exception as e:
        logger.error(f"카테고리 목록 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리 목록을 조회하는 중 오류가 발생했습니다."
        )


@stock_favorites_router.get(
    "/stock-codes",
    response_model=List[str],
    summary="관심기업 종목 코드 목록 조회",
    description="사용자의 관심기업 종목 코드 목록을 조회합니다."
)
async def get_favorite_stock_codes(
    category: Optional[str] = Query(None, description="카테고리명 (선택사항)"),
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """사용자의 관심기업 종목 코드 목록을 조회합니다."""
    try:
        stock_codes = await StockFavoriteService.get_favorite_stock_codes(db, session.user_id, category)
        return stock_codes
    except Exception as e:
        logger.error(f"관심기업 종목 코드 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 종목 코드를 조회하는 중 오류가 발생했습니다."
        )


@stock_favorites_router.post(
    "/",
    response_model=StockFavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="관심기업 추가",
    description="새로운 종목을 관심기업(즐겨찾기)에 추가합니다."
)
async def add_stock_favorite(
    favorite_data: StockFavoriteCreate,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """관심기업에 종목을 추가합니다."""
    try:
        favorite = await StockFavoriteService.add_favorite(
            db=db,
            user_id=session.user_id,
            stock_code=favorite_data.stock_code,
            stock_name=favorite_data.stock_name,
            category=favorite_data.category,
            memo=favorite_data.memo
        )
        return StockFavoriteResponse.from_attributes(favorite)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"관심기업 추가 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 추가 중 오류가 발생했습니다."
        )


@stock_favorites_router.put(
    "/{favorite_id}",
    response_model=StockFavoriteResponse,
    summary="관심기업 수정",
    description="관심기업 정보를 수정합니다."
)
async def update_stock_favorite(
    favorite_id: int = Path(..., description="관심기업 ID"),
    update_data: StockFavoriteUpdate = ...,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """관심기업 정보를 수정합니다."""
    try:
        favorite = await StockFavoriteService.update_favorite(
            db=db,
            user_id=session.user_id,
            favorite_id=favorite_id,
            stock_name=update_data.stock_name,
            category=update_data.category,
            display_order=update_data.display_order,
            memo=update_data.memo
        )
        
        if not favorite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="관심기업을 찾을 수 없습니다."
            )
        
        return StockFavoriteResponse.from_attributes(favorite)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관심기업 수정 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 수정 중 오류가 발생했습니다."
        )


@stock_favorites_router.delete(
    "/{favorite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="관심기업 제거",
    description="관심기업에서 종목을 제거합니다."
)
async def remove_stock_favorite(
    favorite_id: int = Path(..., description="관심기업 ID"),
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """관심기업에서 종목을 제거합니다."""
    try:
        success = await StockFavoriteService.remove_favorite_by_id(db, session.user_id, favorite_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="관심기업을 찾을 수 없습니다."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관심기업 제거 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 제거 중 오류가 발생했습니다."
        )


@stock_favorites_router.post(
    "/toggle",
    response_model=StockFavoriteToggleResponse,
    summary="관심기업 토글",
    description="관심기업 상태를 토글합니다 (추가/제거)."
)
async def toggle_stock_favorite(
    toggle_data: StockFavoriteToggleRequest,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """관심기업 상태를 토글합니다."""
    try:
        is_favorite, favorite = await StockFavoriteService.toggle_favorite(
            db=db,
            user_id=session.user_id,
            stock_code=toggle_data.stock_code,
            stock_name=toggle_data.stock_name,
            category=toggle_data.category
        )
        
        if is_favorite:
            return StockFavoriteToggleResponse(
                is_favorite=True,
                message="관심기업에 추가되었습니다.",
                favorite=StockFavoriteResponse(
                    id=favorite.id,
                    user_id=favorite.user_id,
                    stock_code=favorite.stock_code,
                    stock_name=favorite.stock_name,
                    category=favorite.category,
                    display_order=favorite.display_order,
                    memo=favorite.memo,
                    created_at=favorite.created_at,
                    updated_at=favorite.updated_at
                ) if favorite else None
            )
        else:
            return StockFavoriteToggleResponse(
                is_favorite=False,
                message="관심기업에서 제거되었습니다.",
                favorite=None
            )
    except Exception as e:
        logger.error(f"관심기업 토글 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 상태 변경 중 오류가 발생했습니다."
        )


@stock_favorites_router.get(
    "/check",
    response_model=dict,
    summary="관심기업 확인",
    description="특정 종목이 관심기업에 포함되어 있는지 확인합니다."
)
async def check_stock_favorite(
    stock_code: str = Query(..., description="종목 코드"),
    category: str = Query("default", description="카테고리명"),
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """특정 종목이 관심기업에 포함되어 있는지 확인합니다."""
    try:
        favorite = await StockFavoriteService.check_favorite(db, session.user_id, stock_code, category)
        return {"is_favorite": favorite is not None}
    except Exception as e:
        logger.error(f"관심기업 확인 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 확인 중 오류가 발생했습니다."
        )


@stock_favorites_router.put(
    "/reorder",
    response_model=dict,
    summary="관심기업 순서 재정렬",
    description="카테고리 내 관심기업들의 순서를 재정렬합니다."
)
async def reorder_stock_favorites(
    reorder_data: dict,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """카테고리 내 관심기업들의 순서를 재정렬합니다."""
    try:
        category = reorder_data.get("category")
        stock_code_orders = reorder_data.get("stock_code_orders", [])
        
        if not category or not stock_code_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="카테고리와 순서 정보가 필요합니다."
            )
        
        success = await StockFavoriteService.reorder_favorites(
            db=db,
            user_id=session.user_id,
            category=category,
            stock_code_orders=stock_code_orders
        )
        
        return {"success": success}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관심기업 순서 재정렬 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관심기업 순서 재정렬 중 오류가 발생했습니다."
        )
