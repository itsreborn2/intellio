from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, date

from common.core.database import get_db_async
from stockeasy.models.user_statistics import UserStatistics
from pydantic import BaseModel, Field

# Pydantic 스키마 정의
class UserStat(BaseModel):
    id: int
    stat_type: str
    report_at: datetime
    total_users: int
    new_users: int
    active_users: int
    total_chat_sessions: int
    new_chat_sessions: int
    sessions_per_user: Optional[float] = None
    sessions_per_active_user: Optional[float] = None
    active_user_percentage: Optional[float] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class UserStatListResponse(BaseModel):
    success: bool
    data: List[UserStat]

router = APIRouter(prefix="/stats/users", tags=["User Statistics"])

@router.get("/", response_model=UserStatListResponse)
async def get_user_statistics(
    db: AsyncSession = Depends(get_db_async),
    stat_type: str = Query(..., description="통계 유형 (HOURLY, DAILY, MONTHLY)", enum=["HOURLY", "DAILY", "MONTHLY"]),
    start_date: Optional[date] = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="조회 종료일 (YYYY-MM-DD)")
):
    """
    사용자 통계 데이터를 조회합니다.

    - **stat_type**: 조회할 통계의 유형 (HOURLY, DAILY, MONTHLY) - 필수
    - **start_date**: 조회 기간 시작일
    - **end_date**: 조회 기간 종료일
    """
    query = select(UserStatistics).where(UserStatistics.stat_type == stat_type)

    if start_date:
        query = query.where(UserStatistics.report_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(UserStatistics.report_at <= datetime.combine(end_date, datetime.max.time()))

    query = query.order_by(UserStatistics.report_at.desc())
    
    # 비동기 실행으로 변경
    result = await db.execute(query)
    stats_orm = result.scalars().all()
    
    # SQLAlchemy ORM 객체를 Pydantic 모델로 명시적 변환
    stats = [UserStat.model_validate(stat) for stat in stats_orm]
    
    return {"success": True, "data": stats}
