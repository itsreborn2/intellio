from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

from common.schemas.base import TimestampSchema

class OAuthLoginResponse(BaseModel):
    """OAuth 로그인 응답 스키마"""
    user: dict
    token: str

