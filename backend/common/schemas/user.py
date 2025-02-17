from uuid import UUID
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, constr

from common.schemas.base import BaseSchema, TimestampSchema, ResponseSchema

# 사용자 관련 스키마
class UserBase(BaseSchema):
    """사용자 기본 스키마"""
    email: EmailStr
    name: constr(min_length=2, max_length=50)  # 이름 길이 제한

class UserCreate(UserBase):
    """사용자 생성 스키마"""
    password: constr(min_length=8)  # 비밀번호 최소 8자

class UserUpdate(UserBase):
    """사용자 수정 스키마"""
    password: Optional[constr(min_length=8)] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserLogin(BaseSchema):
    """사용자 로그인 스키마"""
    email: EmailStr
    password: str

class UserInDB(UserBase, TimestampSchema):
    """데이터베이스 사용자 스키마"""
    id: UUID
    is_active: bool = True
    is_superuser: bool = False
    hashed_password: str

class UserResponse(ResponseSchema):
    """사용자 응답 스키마"""
    data: Optional[UserInDB] = None

# 세션 관련 스키마
class SessionBase(BaseSchema):
    """세션 기본 스키마"""
    is_anonymous: bool = False
    user_id: Optional[UUID]

# class SessionBase(SessionBase):
#     """세션 생성 스키마"""
#     user_id: Optional[UUID] = None

class SessionInDB(SessionBase, TimestampSchema):
    """데이터베이스 세션 스키마"""
    id: UUID
    user_id: Optional[UUID] = None
    last_accessed_at: datetime

class SessionUpdate(BaseSchema):
    """세션 업데이트 스키마"""
    user_id: Optional[UUID] = None
    is_anonymous: Optional[bool] = None

class SessionResponse(ResponseSchema):
    """세션 응답 스키마"""
    data: Optional[SessionInDB] = None

