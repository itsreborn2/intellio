from pydantic import BaseModel

class OAuthLoginResponse(BaseModel):
    """OAuth 로그인 응답 스키마"""
    user: dict
    token: str

class TokenData(BaseModel):
    """JWT 토큰 데이터 스키마"""
    user_id: str
    email: str
    provider: str
