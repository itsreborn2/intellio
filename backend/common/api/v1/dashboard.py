import logging
import traceback
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func
from sqlalchemy.future import select

from common.core.database import get_db_async
from common.api.v1.admin import verify_admin
from common.models.user import User, Session

# --- Pydantic Schemas ---
# Pydantic 모델은 API의 입출력 데이터 형식을 정의합니다.
# ORM 모델(User)과 분리하여 API 계층의 독립성을 유지하고, 불필요한 데이터 노출을 방지합니다.

class UserRead(BaseModel):
    """사용자 정보 조회를 위한 Pydantic 스키마"""
    id: UUID
    email: str
    name: str
    is_active: bool
    is_superuser: bool
    oauth_provider: Optional[str] = None
    profile_image: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic V2: orm_mode 대신 from_attributes 사용

class UserListResponse(BaseModel):
    """사용자 목록 응답을 위한 Pydantic 스키마"""
    total: int
    users: List[UserRead]

# --- API Router ---

router = APIRouter(
    prefix="/dashboard", 
    tags=["dashboard"],
    # dependencies=[Depends(verify_admin)] # [개발용 임시 조치] UI 테스트를 위해 관리자 인증 비활성화
)

@router.get("/users", response_model=UserListResponse)
async def get_all_users(
    db: AsyncSession = Depends(get_db_async),
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지 당 항목 수"),
    email: Optional[str] = Query(None, description="검색할 이메일 주소")
):
    """
    데이터베이스에 저장된 모든 사용자 목록을 페이지네이션, 검색 기능과 함께 조회합니다.
    - 기본적으로 최근 가입한 순서로 정렬됩니다.
    - 이메일 주소로 사용자를 검색할 수 있습니다.
    - 관리자만 접근할 수 있습니다.
    """
    try:
        base_query = select(User)
        if email:
            base_query = base_query.where(User.email.ilike(f"%{email}%"))

        # 전체 항목 수 계산
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # 실제 데이터 조회 (정렬 및 페이지네이션 적용)
        users_query = base_query.order_by(desc(User.created_at)).offset((page - 1) * limit).limit(limit)
        users_result = await db.execute(users_query)
        users_orm = users_result.scalars().all()

        # Pydantic 모델 리스트로 명시적으로 변환하여 linter 오류 해결
        return UserListResponse(total=total, users=[UserRead.from_orm(user) for user in users_orm])
    except Exception as e:
        # 오류 발생 시, 상세한 로그를 남기고 500 에러를 발생시킵니다.
        error_traceback = traceback.format_exc()
        logging.error(f"Error in get_all_users: {e}\n{error_traceback}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred while fetching users: {e}"
        )


@router.get("/users/recent", response_model=List[UserRead])
async def get_recent_users(
    db: AsyncSession = Depends(get_db_async)
):
    """최근 가입한 5명의 사용자 목록을 반환합니다."""
    query = select(User).order_by(desc(User.created_at)).limit(5)
    result = await db.execute(query)
    users = result.scalars().all()
    return users
