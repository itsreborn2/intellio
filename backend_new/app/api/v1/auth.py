from uuid import uuid4
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.user import Session
from app.services.user import UserService
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    SessionResponse,
    SessionCreate
)

router = APIRouter(tags=["auth"])

@router.post("/register", response_model=UserResponse)
async def register(
    user_in: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """새로운 사용자 등록 (회원가입)"""
    user_service = UserService(db)
    
    # 이메일 중복 확인
    existing_user = await user_service.get_by_email(user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 이메일입니다."
        )
    
    # 사용자 생성
    user = await user_service.create(user_in)
    
    # 세션 생성
    session_create = SessionCreate(
        session_id=str(uuid4()),
        user_id=user.id,
        is_anonymous=False
    )
    session = await user_service.create_session(session_create)
    
    # 세션 ID를 쿠키에 설정
    response.set_cookie(
        key="session_id",
        value=session.session_id,
        max_age=30 * 24 * 60 * 60,  # 30일
        httponly=True,
        secure=True,  # HTTPS 전용
        samesite="strict"  # CSRF 방지 강화
    )
    
    return UserResponse(
        success=True,
        data=user,
        message="회원가입이 완료되었습니다."
    )

@router.post("/login", response_model=UserResponse)
async def login(
    login_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """사용자 로그인"""
    user_service = UserService(db)
    
    # 사용자 인증
    user = await user_service.authenticate(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    
    # 세션 생성
    session_create = SessionCreate(
        session_id=str(uuid4()),
        user_id=user.id,
        is_anonymous=False
    )
    session = await user_service.create_session(session_create)
    
    # 세션 ID를 쿠키에 설정
    response.set_cookie(
        key="session_id",
        value=session.session_id,
        max_age=30 * 24 * 60 * 60,  # 30일
        httponly=True,
        secure=True,  # HTTPS 전용
        samesite="strict"  # CSRF 방지 강화
    )
    
    return UserResponse(
        success=True,
        data=user,
        message="로그인이 완료되었습니다."
    )

@router.post("/logout")
async def logout(
    response: Response,
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """로그아웃"""
    if session_id:
        user_service = UserService(db)
        await user_service.delete_session(session_id)
    
    # 쿠키에서 세션 ID 제거
    response.delete_cookie(
        key="session_id",
        httponly=True,
        samesite="lax"
    )
    
    return ResponseSchema(
        success=True,
        message="로그아웃되었습니다."
    )
