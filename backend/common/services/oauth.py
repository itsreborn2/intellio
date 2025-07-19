from typing import Dict, Optional
import httpx
import requests
from fastapi import HTTPException
import urllib.parse
from common.core.config import settings
from loguru import logger
import ssl
import secrets
from common.core.redis import redis_client # RedisClient 클래스 대신 싱글톤 인스턴스 import
import json
import time

class OAuthService:
    """OAuth 인증 서비스"""
    
    @staticmethod
    async def get_kakao_token(code: str) -> Dict:
        """카카오 액세스 토큰 획득"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://kauth.kakao.com/oauth/token',
                    data={
                        'grant_type': 'authorization_code',
                        'client_id': settings.KAKAO_CLIENT_ID,
                        'client_secret': settings.KAKAO_CLIENT_SECRET,
                        'code': code,
                        'redirect_uri': settings.KAKAO_REDIRECT_URI
                    }
                )
                return response.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_kakao_user(access_token: str) -> Dict:
        """카카오 사용자 정보 획득"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://kapi.kakao.com/v2/user/me',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                return response.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_google_token(code: str) -> Dict:
        """구글 액세스 토큰 획득"""
        try:
            data = {
                'code': code,
                'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
                'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
                'redirect_uri': settings.GOOGLE_OAUTH_REDIRECT_URI,
                'grant_type': 'authorization_code'
            }
            logger.info(f"Google OAuth 토큰 요청 데이터: {data}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://oauth2.googleapis.com/token',
                    data=data
                )
                response_data = response.json()
                logger.info(f"Google OAuth 토큰 응답: {response_data}")
                
                if 'error' in response_data:
                    error_msg = response_data.get('error_description', response_data['error'])
                    if response_data['error'] == 'invalid_grant':
                        error_msg = '인증 코드가 만료되었거나 이미 사용되었습니다. 다시 로그인해주세요.'
                    raise HTTPException(
                        status_code=400,
                        detail=error_msg
                    )
                return response_data
        except Exception as e:
            logger.error(f"Google OAuth 토큰 요청 실패: {str(e)}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_google_user(access_token: str) -> Dict:
        """구글 사용자 정보 획득"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://www.googleapis.com/oauth2/v2/userinfo',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                user_data = response.json()
                # 구글 응답에서 필요한 데이터를 추출하여 반환
                return {
                    'id': user_data.get('id'),
                    'email': user_data.get('email'),
                    'name': user_data.get('name'),
                    'given_name': user_data.get('given_name'),
                    'family_name': user_data.get('family_name'),
                    'picture': user_data.get('picture'),
                    'locale': user_data.get('locale')
                }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_naver_token(code: str, state: str) -> Dict:
        """네이버 액세스 토큰 획득"""
        try:
            data = {
                'grant_type': 'authorization_code',
                'client_id': settings.NAVER_OAUTH_CLIENT_ID,
                'client_secret': settings.NAVER_OAUTH_CLIENT_SECRET,
                'redirect_uri': settings.NAVER_OAUTH_REDIRECT_URI,
                'code': code,
                'state': state
            }
            logger.info(f"네이버 OAuth 토큰 요청 데이터: {data}")
            
            # WebView 호환을 위한 적절한 헤더 설정
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json'
            }
            
            # httpx로 통일하여 다른 OAuth와 일관성 유지
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://nid.naver.com/oauth2.0/token',
                    data=data,
                    headers=headers
                )
                response_data = response.json()
                logger.info(f"네이버 OAuth 토큰 응답: {response_data}")
                
                if 'error' in response_data:
                    error_msg = response_data.get('error_description', response_data['error'])
                    raise HTTPException(
                        status_code=400,
                        detail=f"네이버 토큰 획득 실패: {error_msg}"
                    )
                return response_data
                
        except Exception as e:
            logger.error(f"네이버 OAuth 토큰 요청 실패: {str(e)}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=400, detail=f"네이버 토큰 획득 중 오류: {str(e)}")
    
    @staticmethod
    async def get_naver_user(access_token: str) -> Dict:
        """네이버 사용자 정보 획득"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://openapi.naver.com/v1/nid/me',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                user_data = response.json()
                if user_data.get('resultcode') != '00':
                    raise HTTPException(
                        status_code=400,
                        detail=f"네이버 사용자 정보 획득 실패: {user_data.get('message')}"
                    )
                
                # 네이버 응답 형식에 맞게 데이터 구조화
                response_data = user_data.get('response', {})
                return {
                    'id': response_data.get('id'),  # 네이버 아이디
                    'email': response_data.get('email'),  # 이메일
                    'name': response_data.get('name'),  # 이름
                    'nickname': response_data.get('nickname'),  # 별명
                    'profile_image': response_data.get('profile_image'),  # 프로필 이미지
                    'age': response_data.get('age'),  # 연령대
                    'gender': response_data.get('gender'),  # 성별
                    'birthday': response_data.get('birthday'),  # 생일
                    'mobile': response_data.get('mobile')  # 전화번호
                }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"네이버 사용자 정보 획득 중 오류: {str(e)}")

    @staticmethod
    def get_authorization_url(provider: str, state: str = None, use_deep_link: bool = False) -> str:
        """OAuth 인증 URL 생성"""
        # 32바이트 랜덤 문자열 추가생성
        state_add_token = state + "__" + secrets.token_hex(16)
        
        # redis_client = RedisClient() # 직접 생성하는 대신 싱글톤 인스턴스 사용
        key = f"oauth_state:{state_add_token}"
        redis_client.set_key(key, state_add_token, expire=300) # 5분간 유효
        logger.info(f"Oauth REDIS set key: {key} - {state_add_token}")
        
        # Intent 방식을 위한 Deep Link URI 설정
        if use_deep_link:
            redirect_uri = f"intellio://oauth/{provider}/callback"
        else:
            # 기존 웹 방식 redirect URI 사용
            redirect_uri = getattr(settings, f"{provider.upper()}_OAUTH_REDIRECT_URI")
        
        if provider == "naver":
            return (
                f"https://nid.naver.com/oauth2.0/authorize"
                f"?response_type=code"
                f"&client_id={settings.NAVER_OAUTH_CLIENT_ID}"
                f"&redirect_uri={redirect_uri}"
                f"&state={state_add_token}"
                f"&scope=name email"
            )
        elif provider == "google":
            # disallowed_useragent 오류 대응을 위한 추가 파라미터
            return (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?response_type=code"
                f"&client_id={settings.GOOGLE_OAUTH_CLIENT_ID}"
                f"&redirect_uri={redirect_uri}"
                f"&state={state_add_token}"
                f"&scope=openid email profile"
                f"&prompt=select_account"  # 계정 선택 강제
                f"&access_type=offline"   # 오프라인 접근
                f"&include_granted_scopes=true"  # 권한 포함
            )
        elif provider == "kakao":
            return (
                f"https://kauth.kakao.com/oauth/authorize"
                f"?response_type=code"
                f"&client_id={settings.KAKAO_OAUTH_CLIENT_ID}"
                f"&redirect_uri={redirect_uri}"
                f"&state={state_add_token}"
                f"&scope=profile_nickname account_email"
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    @staticmethod
    def get_authorization_config(provider: str, state: str = None) -> Dict:
        """OAuth 설정 반환 (Intent 기반 시스템 브라우저 권장)"""
        auth_url = OAuthService.get_authorization_url(provider, state)
        
        return {
            "auth_url": auth_url,
            "intent_strategy": {
                "simple": {
                    "method": "Linking.openURL()",
                    "description": "React Native 기본 방식 (내부적으로 Intent 사용)",
                    "success_rate": "95%"
                },
                "advanced": {
                    "method": "Custom Intent",
                    "chrome_custom_tabs": f"{auth_url}#customtabs=true",
                    "preferred_browser": OAuthService._get_preferred_browser(provider),
                    "fallback_browsers": ["com.android.chrome", "com.android.browser", "org.mozilla.firefox"]
                }
            },
            "webview_fallback": {
                "use_when": "Intent 실패 시",
                "config": {
                    "user_agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36",
                    "javascript_enabled": True,
                    "dom_storage_enabled": True,
                    "shared_cookies_enabled": True
                }
            },
            "error_handling": {
                "no_browser": "webview_fallback",
                "intent_failed": "webview_fallback",
                "user_cancelled": "retry_prompt"
            }
        }
    
    @staticmethod
    def _get_preferred_browser(provider: str) -> Optional[str]:
        """OAuth 제공자별 권장 브라우저 패키지"""
        browser_map = {
            "google": "com.android.chrome",  # 구글은 Chrome 권장
            "naver": None,  # 기본 브라우저 사용
            "kakao": None   # 기본 브라우저 사용
        }
        return browser_map.get(provider)

    @staticmethod
    def get_naver_app_oauth_strategy(provider: str, state: str = None) -> Dict:
        """네이버앱에서 실행 시 최적화된 OAuth 전략"""
        strategies = []
        
        # 1순위: 네이티브 앱 호출 (같은 제공자인 경우)
        if provider == "naver":
            strategies.append({
                "method": "native_app",
                "description": "네이버앱 내 네이티브 로그인",
                "package": "com.nhn.android.search",
                "intent_action": "com.nhn.android.search.action.LOGIN"
            })
        
        # 2순위: Chrome Custom Tabs (가능한 경우)
        strategies.append({
            "method": "custom_tabs",
            "description": "Chrome Custom Tabs 사용",
            "auth_url": OAuthService.get_authorization_url(provider, state, use_deep_link=True),
            "package": "com.android.chrome",
            "custom_tabs_config": {
                "toolbar_color": "#03c75a" if provider == "naver" else "#4285f4" if provider == "google" else "#fee500",
                "show_title": True,
                "url_bar_hiding": True
            }
        })
        
        # 3순위: 시스템 브라우저
        strategies.append({
            "method": "system_browser",
            "description": "시스템 기본 브라우저 사용",
            "auth_url": OAuthService.get_authorization_url(provider, state, use_deep_link=True),
            "intent_action": "android.intent.action.VIEW"
        })
        
        # 4순위: WebView 폴백 (최후 수단)
        strategies.append({
            "method": "webview_fallback",
            "description": "WebView 폴백 (네이버앱 내)",
            "auth_url": OAuthService.get_authorization_url(provider, state, use_deep_link=False),
            "webview_config": {
                "javascript_enabled": True,
                "dom_storage_enabled": True,
                "user_agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 NaverApp/1.0",
                "third_party_cookies": True
            }
        })
        
        return {
            "provider": provider,
            "strategies": strategies,
            "recommended_order": [0, 1, 2, 3],
            "session_bridge_url": f"https://intellio.kr/oauth/bridge/{provider}",
            "error_handling": {
                "intent_failed": "webview_fallback",
                "browser_not_found": "webview_fallback",
                "context_lost": "session_bridge"
            }
        }

    @staticmethod
    async def create_session_bridge(provider: str, oauth_data: Dict, state: str) -> str:
        """네이버앱 컨텍스트 손실 시 세션 브리지 생성"""
        try:
            # Redis에 임시 세션 데이터 저장
            bridge_token = secrets.token_hex(32)
            # redis_client = RedisClient() # 직접 생성하는 대신 싱글톤 인스턴스 사용
            key = f"oauth_bridge:{bridge_token}"
            
            bridge_data = {
                "provider": provider,
                "oauth_data": oauth_data,
                "state": state,
                "timestamp": int(time.time()),
                "origin_app": "naver"
            }
            
            # 5분간 유효한 브리지 토큰
            redis_client.set_key(
                key, 
                json.dumps(bridge_data), 
                expire=300
            )
            
            # 브리지 페이지 URL 반환
            bridge_url = f"https://intellio.kr/oauth/bridge/{provider}?token={bridge_token}"
            logger.info(f"OAuth 세션 브리지 생성: {bridge_url}")
            
            return bridge_url
            
        except Exception as e:
            logger.error(f"세션 브리지 생성 실패: {str(e)}")
            raise HTTPException(status_code=500, detail="세션 브리지 생성 실패")
