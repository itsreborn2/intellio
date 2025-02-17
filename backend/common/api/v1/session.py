from datetime import datetime, timedelta
from typing import Optional
import logging
from fastapi import APIRouter, Depends, Response, Cookie, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.database import get_db_async
from common.models.user import Session
from common.services.user import UserService
from common.schemas.user import SessionResponse, SessionBase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])

@router.post("/", response_model=SessionResponse)
async def create_session(
    response: Response,
    db: AsyncSession = Depends(get_db_async)
):
    """새로운 세션 생성
    
    익명 사용자를 위한 새로운 세션을 생성합니다.
    생성된 세션 ID는 쿠키에 저장됩니다.
    """
    user_service = UserService(db)
    session_create = SessionBase(
        is_anonymous=True
    )
    
    session = await user_service.create_session(session_create)
    
    # 세션 ID를 쿠키에 설정
    response.set_cookie(
        key="session_id",
        value=session.id,
        max_age=30 * 24 * 60 * 60,  # 30일
        httponly=True,
        secure=True,  # HTTPS 전용
        samesite="strict"  # CSRF 방지 강화
    )
    
    return session

@router.get("/current", response_model=SessionResponse)
async def get_current_session(
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db_async)
):
    """현재 세션 정보 조회"""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="세션이 존재하지 않습니다."
        )
    
    user_service = UserService(db)
    session = await user_service.get_active_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 세션입니다."
        )
    
    return session

@router.delete("/current")
async def delete_current_session(
    response: Response,
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db_async)
):
    """현재 세션 삭제"""
    if session_id:
        user_service = UserService(db)
        await user_service.delete_session(session_id)
    
    # 쿠키에서 세션 ID 제거
    response.delete_cookie(
        key="session_id",
        httponly=True,
        secure=True,  # HTTPS 전용
        samesite="strict"  # CSRF 방지 강화
    )
    
    return {"message": "세션이 삭제되었습니다."}

@router.post("/cleanup")
async def cleanup_expired_sessions(
    db: AsyncSession = Depends(get_db_async)
):
    """만료된 세션 정리"""
    user_service = UserService(db)
    deleted_count = await user_service.cleanup_expired_sessions()
    return {
        "message": f"{deleted_count}개의 만료된 세션이 정리되었습니다."
    }
