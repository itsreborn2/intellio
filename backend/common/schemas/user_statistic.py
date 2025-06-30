from pydantic import BaseModel
from datetime import date, datetime

class UserStatisticBase(BaseModel):
    """
    사용자 통계 기본 스키마
    """
    date: date
    total_users: int
    new_users: int
    active_users: int
    total_sessions: int
    new_sessions: int

class UserStatisticCreate(UserStatisticBase):
    """
    사용자 통계 생성 스키마
    """
    pass

class UserStatisticInDB(UserStatisticBase):
    """
    DB에 저장된 사용자 통계 스키마
    """
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
