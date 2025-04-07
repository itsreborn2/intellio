from typing import Dict, Optional
import httpx
import requests
from fastapi import HTTPException
import urllib.parse
from common.core.config import settings
from loguru import logger
import ssl
import secrets
from common.core.redis import RedisClient

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
                'state': state  #settings.NAVER_OAUTH_STATE
            }
            logger.info(f"Naver token request data: {data}")
            logger.info(f"Naver token request URL: https://nid.naver.com/oauth2.0/token")
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                #'User-Agent': 'curl/7.88.1'
                'X-Naver-Client-Id':settings.NAVER_OAUTH_CLIENT_ID,
                'X-Naver-Client-Secret': settings.NAVER_OAUTH_CLIENT_SECRET
            }
            logger.info(f"Naver token request headers: {headers}")
            url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={settings.NAVER_OAUTH_CLIENT_ID}&client_secret={settings.NAVER_OAUTH_CLIENT_SECRET}&redirect_uri={settings.NAVER_OAUTH_REDIRECT_URI}&code={code}&state={state}"
            
            
            try:
                response = requests.get(url, headers=headers)
                logger.info(f"Naver token response status: {response.status_code}")
                logger.info(f"Naver token response headers: {dict(response.headers)}")
                response_text = response.text
                logger.info(f"Naver token response body: {response_text}")            
                token_data = response.json()
                return token_data
            except Exception as e:
                logger.error(f"Naver token request fail : {str(e)}", exc_info=True)
                raise HTTPException(status_code=400, detail=str(e))
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"네이버 토큰 획득 중 상세 오류: {str(e)}", exc_info=True)
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
    def get_authorization_url(provider: str, state:str=None) -> str:
        #backend_url = settings.FASTAPI_URL
        """OAuth 인증 URL 생성"""
        # 32바이트 랜덤 문자열 추가생성
        state_add_token = state + "__" + secrets.token_hex(16)
        # www.intellio.kr__token_string
        
        redis_client = RedisClient()
        redis_client.set_key(f"oauth_state:{state_add_token}", state_add_token, expire=180)
        logger.info(f"Auth REDIS set key :  'oauth_state:{state_add_token}'")
        if provider == "naver":
            return (
                f"https://nid.naver.com/oauth2.0/authorize"
                f"?response_type=code"
                f"&client_id={settings.NAVER_OAUTH_CLIENT_ID}"
                f"&redirect_uri={settings.NAVER_OAUTH_REDIRECT_URI}"
                f"&state={state_add_token}"
                f"&scope=name email"
            )
        elif provider == "google":
            return (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?response_type=code"
                f"&client_id={settings.GOOGLE_OAUTH_CLIENT_ID}"
                f"&redirect_uri={settings.GOOGLE_OAUTH_REDIRECT_URI}"
                f"&state={state_add_token}"
                f"&scope=openid email profile"
            )
        elif provider == "kakao":
            return (
                f"https://kauth.kakao.com/oauth/authorize"
                f"?response_type=code"
                f"&client_id={settings.KAKAO_OAUTH_CLIENT_ID}"
                f"&redirect_uri={settings.KAKAO_OAUTH_REDIRECT_URI}"
                f"&state={state_add_token}"
                f"&scope=profile_nickname account_email"
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")
