from uuid import uuid4
from typing import Optional
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from common.core.exceptions import AuthenticationRedirectException
from common.core.database import get_db_async
from common.models.user import Session
from common.services.user import UserService
from common.services.oauth import OAuthService
from common.core.security import create_oauth_token, verify_oauth_token
from common.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    SessionResponse,
    SessionBase
)
from common.schemas.auth import OAuthLoginResponse
from common.core.config import settings
import json
#import logging
from loguru import logger

router = APIRouter(prefix="/auth", tags=["auth"])
#logger = logging.getLogger(__name__)

# OAuth2 bearer token 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/login", response_model=UserResponse)
async def login(
    login_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db_async)
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
    session_create = SessionBase(
        user_id=user.id,
        is_anonymous=False
    )
    session = await user_service.create_session(session_create)
    
    # 세션 ID를 쿠키에 설정
    response.set_cookie(
        key="session_id",
        value=session.id,
        max_age=30 * 24 * 60 * 60,  # 30일
        httponly=True,
        secure=settings.COOKIE_SECURE,  # production에서만 True
        samesite="lax",

        path="/",  # 모든 경로에서 접근 가능
        domain=settings.COOKIE_DOMAIN  # 환경별 도메인 설정
    )
    
    return UserResponse(
        success=True,
        data=user,
        message="로그인이 완료되었습니다."
    )

@router.post("/logout", response_model=SessionResponse)
async def logout(
    response: Response,
    session_id: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db_async)
):
    """로그아웃 처리 - 세션 삭제 및 쿠키 제거"""
    if not session_id:
        return SessionResponse(
            success=True,
            message="이미 로그아웃 되었습니다."
        )
    
    user_service = UserService(db)
    # 세션 삭제
    await user_service.delete_session(session_id)
    
    # 쿠키에서 세션 ID 제거
    response.delete_cookie(
        key="session_id",
        path="/",
        domain=settings.COOKIE_DOMAIN
    )
    
    return SessionResponse(
        success=True,
        message="로그아웃되었습니다."
    )

@router.get("/{provider}/login")
async def oauth_login(provider: str):
    """소셜 로그인 시작점"""
    oauth_service = OAuthService()
    url = oauth_service.get_authorization_url(provider)
    logger.info(f"oauth_login : {url}")
    return RedirectResponse(url)

@router.post("/{provider}/callback", response_model=OAuthLoginResponse)
@router.get("/{provider}/callback", response_model=OAuthLoginResponse)
async def oauth_callback(
    provider: str,
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db_async),
    state: Optional[str] = None
):
    """OAuth 콜백 처리"""
    oauth_service = OAuthService()
    user_service = UserService(db)
    
    try:
        # 제공자별 토큰 및 사용자 정보 획득
        if provider == "kakao":
            token_info = await oauth_service.get_kakao_token(code)
            user_info = await oauth_service.get_kakao_user(token_info["access_token"])
        elif provider == "google":
            token_info = await oauth_service.get_google_token(code)
            if "access_token" not in token_info:
                logger.error(f"OAuth callback error: access_token 미발견. token_info: {token_info}")
                raise HTTPException(status_code=400, detail="access_token이 응답에 포함되어 있지 않습니다.")
            user_info = await oauth_service.get_google_user(token_info["access_token"])
        elif provider == "naver":
            token_info = await oauth_service.get_naver_token(code)
            logger.info(f"Naver token info: {token_info}")
            user_info = await oauth_service.get_naver_user(token_info["access_token"])
            logger.info(f"Naver user info: {user_info}")
        else:
            raise HTTPException(status_code=400, detail="Invalid provider")

        # 사용자 정보로 DB에서 사용자 조회 또는 생성
        oauth_id = str(user_info.get("id"))
        if not oauth_id:
            raise HTTPException(status_code=400, detail="Failed to get user ID from provider")
            
        email = user_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Failed to get email from provider")
        
        user = await user_service.get_by_oauth(provider, oauth_id)
        if not user:
            logger.info(f"Creating new user with email: {provider}")
            # 새 사용자 생성
            user = await user_service.create_oauth_user({
                "email": email,
                "oauth_provider": provider,
                "oauth_provider_id": oauth_id,
                "name": user_info.get("nickname") or user_info.get("name") or email.split("@")[0]
            })
        else:
            logger.info(f"Exsisting user with ID: {provider}, {user.id}, {user.email}")
        
        # 세션 생성
        session_create = SessionBase(
            user_id=user.id,
            is_anonymous=False  # OAuth 로그인 사용자는 익명이 아님
        )
        session = await user_service.create_session(session_create)
        logger.info(f"Created new session: {session.id} for user: {user.email}")
        
        # JWT 토큰 생성
        token = create_oauth_token({
            "sub": str(user.id),
            "email": user.email,
            "provider": provider
        })
        logger.info(f"Created token : {token}")

        # 세션 ID를 쿠키로 설정
        # 로그인 후 무조건 settings.FRONTEND_URL로 redirect 하는데. 도메인이 3군데. 
        # 아마 각 서비스에서 직접 로그인을 할 경우도 있을테니, redirect 하는 지점을 적절하게 조절해야겠네.
        response = RedirectResponse(url=f"{settings.DOCEASY_URL}/")
        response.set_cookie(
            key="session_id",
            value=session.id,
            max_age=30 * 24 * 60 * 60,  # 30일
            httponly=True,
            secure=settings.COOKIE_SECURE,  # production에서만 True
            samesite="lax",
            path="/",  # 모든 경로에서 접근 가능
            domain=settings.COOKIE_DOMAIN  # 환경별 도메인 설정
        )
        
        # JWT 토큰도 쿠키로 설정
        response.set_cookie(
            key="token",
            value=token,
            max_age=30 * 24 * 60 * 60,  # 30일
            httponly=False,  # JavaScript에서 접근 가능하도록
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            path="/",
            domain=settings.COOKIE_DOMAIN
        )

        # 사용자 정보도 쿠키로 설정
        user_data = {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "provider": provider
        }
        # URL 인코딩을 사용하여 한글 문자를 안전하게 처리
        encoded_user_data = urllib.parse.quote(
            json.dumps(user_data, ensure_ascii=False).replace(',', '|')
        )
        response.set_cookie(
            key="user",
            value=encoded_user_data,
            max_age=30 * 24 * 60 * 60,
            httponly=False,  # JavaScript에서 접근 가능하도록
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            path="/",
            domain=settings.COOKIE_DOMAIN
        )

        return response
        
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        # 에러 발생 시 에러 페이지로 리다이렉트
        error_message = urllib.parse.quote(str(e))
        #return RedirectResponse(url=f"{settings.DOCEASY_URL}/auth/error?message={error_message}")
        raise AuthenticationRedirectException(f'{settings.INTELLIO_URL}/error')

@router.get("/me", response_model=OAuthLoginResponse)
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_async)
):
    """현재 로그인한 사용자 정보 조회"""
    token_data = verify_oauth_token(token)
    user_service = UserService(db)
    user = await user_service.get(token_data["sub"])
    logger.info(f"[get_current_user] - ID: {user.id}, email: {user.email}, provider: {user.oauth_provider}")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "provider": user.oauth_provider
        },
        "token": token
    }
