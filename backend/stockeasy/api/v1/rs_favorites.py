"""
RS 즐겨찾기 API 라우터.

RS 즐겨찾기 관련 API 엔드포인트를 제공합니다.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from common.core.database import get_db_async
from common.core.deps import get_current_session
from common.models.user import Session
from stockeasy.schemas.rs_favorites import (
    RSFavoriteResponse,
    RSFavoriteToggleRequest,
    RSFavoriteToggleResponse
)
from stockeasy.services.rs_favorite_service import RSFavoriteService


rs_favorites_router = APIRouter(prefix="/rs-favorites", tags=["RS 즐겨찾기"])


@rs_favorites_router.get(
    "/",
    response_model=List[RSFavoriteResponse],
    summary="RS 즐겨찾기 목록 조회",
    description="현재 사용자의 RS 즐겨찾기 종목 목록을 조회합니다."
)
async def get_rs_favorites(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """RS 즐겨찾기 목록을 조회합니다."""
    try:
        favorites = await RSFavoriteService.get_favorites_by_user_id(db, session.user_id)
        
        logger.info(f"사용자 {session.user_id}의 RS 즐겨찾기 {len(favorites)}개 조회")
        return [RSFavoriteResponse.from_orm(favorite) for favorite in favorites]
        
    except Exception as e:
        logger.error(f"RS 즐겨찾기 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RS 즐겨찾기 목록을 조회하는 중 오류가 발생했습니다."
        )


@rs_favorites_router.post(
    "/toggle",
    response_model=RSFavoriteToggleResponse,
    summary="RS 즐겨찾기 토글",
    description="RS 즐겨찾기를 토글합니다. 즐겨찾기에 있으면 제거하고, 없으면 추가합니다."
)
async def toggle_rs_favorite(
    request: RSFavoriteToggleRequest,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """RS 즐겨찾기를 토글합니다."""
    try:
        is_favorite, favorite = await RSFavoriteService.toggle_favorite(
            db, session.user_id, request.stock_code, request.stock_name
        )
        
        if is_favorite:
            message = "즐겨찾기에 추가되었습니다."
            favorite_response = RSFavoriteResponse.from_orm(favorite) if favorite else None
        else:
            message = "즐겨찾기에서 제거되었습니다."
            favorite_response = None
        
        logger.info(f"사용자 {session.user_id}가 종목 {request.stock_code} RS 즐겨찾기 토글: {is_favorite}")
        
        return RSFavoriteToggleResponse(
            is_favorite=is_favorite,
            message=message,
            favorite=favorite_response
        )
        
    except ValueError as e:
        logger.warning(f"RS 즐겨찾기 토글 실패 (사용자 오류): {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"RS 즐겨찾기 토글 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RS 즐겨찾기를 처리하는 중 오류가 발생했습니다."
        )


@rs_favorites_router.get(
    "/stock-codes",
    response_model=List[str],
    summary="RS 즐겨찾기 종목 코드 목록 조회",
    description="현재 사용자의 RS 즐겨찾기 종목 코드 목록을 조회합니다."
)
async def get_rs_favorite_stock_codes(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """RS 즐겨찾기 종목 코드 목록을 조회합니다."""
    try:
        stock_codes = await RSFavoriteService.get_favorite_stock_codes(db, session.user_id)
        
        logger.info(f"사용자 {session.user_id}의 RS 즐겨찾기 종목 코드 {len(stock_codes)}개 조회")
        return stock_codes
        
    except Exception as e:
        logger.error(f"RS 즐겨찾기 종목 코드 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RS 즐겨찾기 종목 코드 목록을 조회하는 중 오류가 발생했습니다."
        )


@rs_favorites_router.get(
    "/check/{stock_code}",
    response_model=bool,
    summary="RS 즐겨찾기 여부 확인",
    description="특정 종목이 현재 사용자의 RS 즐겨찾기에 있는지 확인합니다."
)
async def check_rs_favorite(
    stock_code: str,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_async)
):
    """특정 종목의 RS 즐겨찾기 여부를 확인합니다."""
    try:
        is_favorite = await RSFavoriteService.is_favorite(db, session.user_id, stock_code)
        
        logger.info(f"사용자 {session.user_id}의 종목 {stock_code} RS 즐겨찾기 여부: {is_favorite}")
        return is_favorite
        
    except Exception as e:
        logger.error(f"RS 즐겨찾기 여부 확인 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RS 즐겨찾기 여부를 확인하는 중 오류가 발생했습니다."
        )
