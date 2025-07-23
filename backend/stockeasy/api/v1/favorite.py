from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from common.core.database import get_db_async
from common.core.deps import get_current_session
from common.models.user import Session
from stockeasy.services.favorite_service import FavoriteService
from stockeasy.schemas.favorite import FavoriteCreate, FavoriteResponse

favorite_router = APIRouter(prefix="/favorites", tags=["즐겨찾기"])


@favorite_router.get("", response_model=List[FavoriteResponse])
async def get_favorites(
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session),
):
    """현재 로그인된 사용자의 즐겨찾기 목록을 조회합니다."""
    try:
        favorites = await FavoriteService.get_favorites_by_user_id(db, current_session.user_id)
        return [FavoriteResponse.from_orm(fav) for fav in favorites]
    except Exception as e:
        logger.error(f"즐겨찾기 목록 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="즐겨찾기 목록을 가져오는 중 오류가 발생했습니다.",
        )


@favorite_router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    favorite: FavoriteCreate,
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session),
):
    """새로운 주식을 즐겨찾기에 추가합니다."""
    try:
        new_favorite = await FavoriteService.add_favorite(
            db, current_session.user_id, favorite.stock_code, favorite.stock_name
        )
        return FavoriteResponse.from_orm(new_favorite)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"즐겨찾기 추가 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="즐겨찾기 추가 중 오류가 발생했습니다.",
        )


@favorite_router.delete("/{stock_code}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    stock_code: str = Path(..., description="삭제할 종목 코드"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session),
):
    """즐겨찾기에서 주식을 삭제합니다."""
    try:
        success = await FavoriteService.remove_favorite(
            db, current_session.user_id, stock_code
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="해당 종목을 즐겨찾기에서 찾을 수 없습니다."
            )
    except Exception as e:
        logger.error(f"즐겨찾기 삭제 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="즐겨찾기 삭제 중 오류가 발생했습니다.",
        )
