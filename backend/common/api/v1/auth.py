from uuid import uuid4
from typing import Optional
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie, status
from httpx import request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse, JSONResponse
from common.core.redis import RedisClient
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
    SessionBase,
    UserUpdate
)
from common.schemas.auth import OAuthLoginResponse
from common.core.config import settings
import json
from loguru import logger
from datetime import datetime, timedelta

from pydantic import ValidationError

router = APIRouter(prefix="/auth", tags=["auth"])

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
        user_email=user.email,
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
        domain=".intellio.kr" if settings.ENV == "production" else "localhost"
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
    logger.info(f"logout - session_id: {session_id}")
    user_service = UserService(db)
    # 세션 삭제
    await user_service.delete_session(session_id)
    
    # 쿠키에서 세션 ID 제거
    response.delete_cookie(
        key="session_id",
        path="/",
        domain=".intellio.kr" if settings.ENV == "production" else None,
        secure=True,
        samesite="lax"
    )
    
    # token 쿠키 제거
    response.delete_cookie(
        key="token",
        path="/",
        domain=".intellio.kr" if settings.ENV == "production" else None,
        secure=True,
        samesite="lax"
    )
    
    # user 쿠키 제거
    response.delete_cookie(
        key="user",
        path="/",
        domain=".intellio.kr" if settings.ENV == "production" else None,
        secure=True,
        samesite="lax"
    )
    
    return SessionResponse(
        success=True,
        message="로그아웃되었습니다."
    )

@router.get("/{provider}/login")
async def oauth_login(provider: str, request: Request, redirectTo: Optional[str] = None):
    """소셜 로그인 시작점"""
    # 요청 출처 확인
    referer = request.headers.get('referer')
    origin = request.headers.get('origin')
    # 로그 출력
    logger.info(f"Login request from referer: {referer}, origin: {origin}")
    # Login request from referer: http://localhost:3000/
    # Login request from referer: http://localhost:3010/
    # INTELLIO_URL=https://www.intellio.kr
    # DOCEASY_URL =https://doceasy.intellio.kr
    # INTELLIO_URL=http://localhost:3000
    # DOCEASY_URL =http://localhost:3010
    
    # referer가 None인 경우 처리
    if not referer:
        logger.warning("Referer 헤더가 없음. redirectTo 파라미터 확인")
        if redirectTo:
            if redirectTo == "doceasy":
                redirect_to = f"{settings.DOCEASY_URL}"
            elif redirectTo == "stockeasy":
                redirect_to = f"{settings.STOCKEASY_URL}"
            elif redirectTo == "intellio" or redirectTo == "/":
                redirect_to = f"{settings.INTELLIO_URL}"
            else:
                raise HTTPException(status_code=400, detail="유효하지 않은 redirectTo 값")
        else:
            # 기본값으로 INTELLIO_URL 사용
            redirect_to = f"{settings.INTELLIO_URL}"
        
        logger.info(f"Referer 없음, 기본 redirect_to 설정: {redirect_to}")
    else:
        redirect_domain = referer.split('/')[2]
        redirect_to = redirect_domain
        logger.info(f"referer domain_only: {redirect_domain}")

        # 요청 보낸곳으로 되돌리기.
        if redirect_domain in settings.INTELLIO_URL: # https://www.intellio.kr
            redirect_to = f"{settings.INTELLIO_URL}"
        elif redirect_domain in settings.DOCEASY_URL: # https://www.intellio.kr:
            redirect_to = f"{settings.DOCEASY_URL}"
        elif redirect_domain in settings.STOCKEASY_URL: # https://stockeasy.intellio.kr
            redirect_to = f"{settings.STOCKEASY_URL}"
        else:
            raise HTTPException(status_code=400, detail="Your domain is not valid")
    
    # redirectTo가 명시적으로 있다면, 거기로 리다이렉트.
    if redirectTo:
        if redirectTo == "doceasy":  # url로 검색하면 안됨. localhost는 체크못함.
            redirect_to = f"{settings.DOCEASY_URL}"
        elif redirectTo == "stockeasy":
            redirect_to = f"{settings.STOCKEASY_URL}"
        elif redirectTo == "intellio" or redirectTo == "/":
            redirect_to = f"{settings.INTELLIO_URL}"
        else:
            raise HTTPException(status_code=400, detail="Invalid redirectTo")

    oauth_service = OAuthService()
    url = oauth_service.get_authorization_url(provider, state=redirect_to)
    logger.info(f"oauth_login : {url}")
    return RedirectResponse(url)

@router.post("/{provider}/callback", response_model=OAuthLoginResponse)
@router.get("/{provider}/callback", response_model=OAuthLoginResponse)
async def oauth_callback(
    provider: str,
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_db_async),
    state: Optional[str] = None,
    redirect_uri: Optional[str] = None
):
    """OAuth 콜백 처리"""
    oauth_service = OAuthService()
    user_service = UserService(db)
    
    try:
        if state:
            t = state.split("__")
            if len(t) == 2:
                redirect_url = t[0]
                recv_token = t[1]
            else:
                raise HTTPException(status_code=400, detail="Invalid state")
        # 제공자별 토큰 및 사용자 정보 획득
        logger.info(f"oauth_callback - provider: {provider}, code: {code}, state: {state}, redirect_uri: {redirect_url}")
        # state: http://localhost:3000/::token_string, redirect_uri: None

                
        redis_client = RedisClient()
        key = f"oauth_state:{state}"
        
        stored_state = redis_client.get_key(key)
        logger.info(f"Auth REDIS get key: {key} - {stored_state}")
        if not stored_state or stored_state != state:
            logger.info(f"oauth_callback - stored_state: {stored_state}, state: {state}")
            raise HTTPException(
                status_code=400,
                detail="Invalid OAuth state parameter"
            )
        redis_client.delete_key(f"oauth_state:{state}")

        if provider == "kakao":
            token_info = await oauth_service.get_kakao_token(code)
            user_info = await oauth_service.get_kakao_user(token_info["access_token"])
        elif provider == "google":
            token_info = await oauth_service.get_google_token(code)
            user_info = await oauth_service.get_google_user(token_info["access_token"])
        elif provider == "naver":
            token_info = await oauth_service.get_naver_token(code, state)
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
        profile_image = user_info.get("picture") or user_info.get("profile_image")
        user = await user_service.get_by_oauth(provider, oauth_id)
        if not user:
            
            logger.info(f"Creating new user with email: {provider}, profile_image: {profile_image}")
            # 새 사용자 생성
            user = await user_service.create_oauth_user({
                "email": email,
                "oauth_provider": provider,
                "oauth_provider_id": oauth_id,
                "name": user_info.get("nickname") or user_info.get("name") or email.split("@")[0],
                "profile_image": user_info.get("picture") or user_info.get("profile_image")
            })
        else:
            logger.info(f"Existing user with ID: {provider}, {user.id}, {user.email}, {profile_image}")
            
            # 사용자 활동 시간 업데이트
            user_service = UserService(db)
            await user_service.update_user_last_activity(user.id)
            # 프로필 이미지가 변경되었다면 업데이트
            if profile_image and profile_image != user.profile_image:
                logger.info(f"Updating profile image for user {user.id} from {user.profile_image} to {profile_image}")
                # UserUpdate에는 email과 name 필드가 필수이므로 기존 사용자 데이터에서 가져옴
                update_data = {
                    "email": user.email,
                    "name": user.name,
                    "profile_image": profile_image
                }
                user = await user_service.update(user.id, UserUpdate(**update_data))
        
        # 세션 생성
        session_create = SessionBase(
            user_id=user.id,
            user_email=user.email,
            is_anonymous=False
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

        # 사용자 정보
        user_data = {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "provider": provider
        }
        
        # profile_image가 있을 경우에만 추가
        if user.profile_image:
            user_data["profile_image"] = user.profile_image

        # URL 인코딩을 사용하여 한글 문자를 안전하게 처리
        encoded_user_data = urllib.parse.quote(
            json.dumps(user_data, ensure_ascii=False)  # 순수 JSON 문자열 인코딩
        )

        # 리다이렉트 URL 결정
        if not redirect_url.startswith('http://')  and not redirect_url.startswith('https://'):
            # 개발 환경에서는 http, 프로덕션에서는 https 사용
            logger.info(f" ENV 체크 : {settings.ENV}")
            scheme = "https://" if settings.ENV == "production" else "http://"
            redirect_url = f"{scheme}{redirect_url}"

        redirect_to = f"{redirect_url}/auth/callback?success=true&token={token}&user={encoded_user_data}"
        logger.info(f"final - oauth_callback - redirect_to: {redirect_to}")
        
        # 먼저 응답 생성 (Response 객체 사용)
        response = Response()
        
        # 세션 ID 쿠키 설정
        response.set_cookie(
            key="session_id",
            value=session.id,
            max_age=30 * 24 * 60 * 60,  # 30일
            httponly=True,
            secure=settings.ENV == "production",  # 개발 환경에서는 False
            samesite="lax",
            path="/",
            domain=".intellio.kr" if settings.ENV == "production" else "localhost"
        )
        
        # JWT 토큰 쿠키 설정
        response.set_cookie(
            key="token",
            value=token,
            max_age=30 * 24 * 60 * 60,
            httponly=False,  # JavaScript에서 접근 가능하도록
            secure=settings.ENV == "production",  # 개발 환경에서는 False
            samesite="lax",
            path="/",
            domain=".intellio.kr" if settings.ENV == "production" else "localhost"
        )

        # 사용자 정보 쿠키 설정
        response.set_cookie(
            key="user",
            value=encoded_user_data,
            max_age=30 * 24 * 60 * 60,
            httponly=False,  # JavaScript에서 접근 가능하도록
            secure=settings.ENV == "production",  # 개발 환경에서는 False
            samesite="lax",
            path="/",
            domain=".intellio.kr" if settings.ENV == "production" else "localhost"
        )
        
        # 쿠키 설정 후 리다이렉션
        response.headers["Location"] = redirect_to
        response.status_code = status.HTTP_302_FOUND


        return response
        
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        error_message = urllib.parse.quote(str(e))
        # 에러 발생 시는 프론트로 에러 메시지 화면 리다이렉트
        redirect_to = f"{settings.DOCEASY_URL}/auth/callback?success=false&error={error_message}"
        return RedirectResponse(url=redirect_to)

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
