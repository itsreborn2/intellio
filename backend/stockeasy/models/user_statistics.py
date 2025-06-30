from sqlalchemy import Column, Integer, String, DateTime, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from common.models.base import Base

class UserStatistics(Base):
    """
    사용자 활동 및 통계 데이터를 저장하는 모델.
    시간별, 일별, 월별 데이터를 stat_type으로 구분하여 기록합니다.
    """
    __tablename__ = 'user_statistics'
    __table_args__ = ({"schema": "stockeasy"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 통계 기본 정보
    stat_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="통계 유형 (HOURLY, DAILY, MONTHLY)")
    report_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="통계 집계 기준 시각")
    
    # 사용자 통계
    total_users: Mapped[int] = mapped_column(Integer, nullable=False, comment="누적 전체 사용자 수")
    new_users: Mapped[int] = mapped_column(Integer, nullable=False, comment="해당 기간 신규 가입자 수")
    active_users: Mapped[int] = mapped_column(Integer, nullable=False, comment="해당 기간 활성 사용자 수")
    
    # 채팅 세션 통계
    total_chat_sessions: Mapped[int] = mapped_column(Integer, nullable=False, comment="누적 전체 채팅 세션 수")
    new_chat_sessions: Mapped[int] = mapped_column(Integer, nullable=False, comment="해당 기간 신규 채팅 세션 수")
    
    # 계산된 비율 통계
    sessions_per_user: Mapped[float] = mapped_column(Float, comment="전체채팅/전체사용자", nullable=True)
    sessions_per_active_user: Mapped[float] = mapped_column(Float, comment="오늘채팅/오늘사용자", nullable=True)
    active_user_percentage: Mapped[float] = mapped_column(Float, comment="오늘사용자/전체사용자", nullable=True)
    
    # 레코드 생성 시각
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="레코드 생성 시각")

    def __repr__(self):
        return f"<UserStatistics(id={self.id}, type='{self.stat_type}', report_at='{self.report_at}')>"
