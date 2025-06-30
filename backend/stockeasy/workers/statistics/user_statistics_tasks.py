"""
사용자 통계 데이터 처리 태스크

이 모듈은 주기적으로 실행되어 사용자 활동 데이터를 수집하고,
통계를 생성하여 데이터베이스에 저장하는 Celery 태스크를 포함합니다.
과거 CSV 데이터와의 일관성을 보장하는 로직을 따릅니다.

- HOURLY: 매시간 그날 0시부터 현재까지의 '누적' 통계를 기록합니다.
- DAILY: 매일 23시 50분 이후, 그날의 최종 HOURLY 데이터를 복사하여 일일 통계로 저장합니다.
- MONTHLY: 매월 말일, 해당 월의 DAILY 통계들을 집계하여 월간 통계로 저장합니다.
"""
import logging
from datetime import datetime, timedelta
import calendar
from sqlalchemy import func
from sqlalchemy.orm import Session

from common.core.config import settings
from common.core.database import SessionLocal
from common.models.user import User
from stockeasy.core.celery_app import celery
from stockeasy.models.chat import StockChatSession
from stockeasy.models.user_statistics import UserStatistics

logger = logging.getLogger(__name__)


@celery.task(
    bind=True,
    name="stockeasy.workers.statistics.user_statistics_tasks.record_user_statistics",
    queue="general-periodic",
    max_retries=3,
    soft_time_limit=600,
    time_limit=700,
    acks_late=True,
    reject_on_worker_lost=True
)
def record_user_statistics(self):
    """
    매시 50-59분 사이에 실행되는 태스크.
    그날 0시부터 현재까지의 '누적' 사용자 통계를 계산하여 'HOURLY' 레코드로 저장합니다.
    하루의 마지막 실행 시(23:50 이후)에는 'DAILY' 레코드도 함께 저장합니다.
    """
    # 운영 환경에서만 실행 (개발 테스트를 위해 임시 주석 처리)
    # if settings.ENVIRONMENT != "production":
    #     logger.info("개발 환경에서는 사용자 통계를 기록하지 않습니다.")
    #     return

    dtNow = datetime.now()
    # 매시 50분에서 59분 사이에만 실행
    if dtNow.minute < 50:
        return

    today_date = dtNow.date()
    start_of_day = datetime.combine(today_date, datetime.min.time())

    logger.info(f"사용자 통계 생성 시작: {dtNow.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        with SessionLocal() as db:
            # 1. 통계 데이터 수집 (오늘 0시부터 현재시간 dtNow 까지의 누적값)
            total_users = get_total_users_sync(db)
            active_users_today = get_active_users_sync(db, start_of_day, dtNow).get('total', 0)
            new_users_today = get_new_users_sync(db, start_of_day, dtNow).get('total', 0)
            total_sessions = get_total_chat_sessions_sync(db).get('total', 0)
            new_sessions_today = get_daily_chat_sessions_sync(db, start_of_day, dtNow).get('total', 0)

            logger.info(f"DB 통계 조회 결과: 전체 사용자={total_users}, 활성={active_users_today}, "
                        f"신규={new_users_today}, 전체 세션={total_sessions}, 신규 세션={new_sessions_today}")

            # 2. 비율 계산
            sessions_per_user = (total_sessions / total_users) if total_users > 0 else 0
            sessions_per_active_user = (new_sessions_today / active_users_today) if active_users_today > 0 else 0
            active_user_percentage = (active_users_today / total_users) * 100 if total_users > 0 else 0

            # 3. 'HOURLY' 통계 DB 저장
            hourly_stat = UserStatistics(
                stat_type='HOURLY',
                report_at=dtNow,
                total_users=total_users,
                new_users=new_users_today,
                active_users=active_users_today,
                total_chat_sessions=total_sessions,
                new_chat_sessions=new_sessions_today,
                sessions_per_user=sessions_per_user,
                sessions_per_active_user=sessions_per_active_user,
                active_user_percentage=active_user_percentage
            )
            db.add(hourly_stat)
            logger.info(f"HOURLY 통계 저장 완료: {dtNow.strftime('%Y-%m-%d %H:%M')}")

            # 4. 하루의 마지막 통계(23:50 이후)일 경우 'DAILY' 통계도 저장
            if dtNow.hour == 23 and dtNow.minute >= 50:
                # 일일 통계는 해당 날짜의 마지막 시간으로 기록하여 CSV 데이터 형식과 일관성을 맞춤
                daily_report_time = dtNow.replace(hour=23, minute=59, second=59)
                daily_stat = UserStatistics(
                    stat_type='DAILY',
                    report_at=daily_report_time,
                    total_users=total_users,
                    new_users=new_users_today,
                    active_users=active_users_today,
                    total_chat_sessions=total_sessions,
                    new_chat_sessions=new_sessions_today,
                    sessions_per_user=sessions_per_user,
                    sessions_per_active_user=sessions_per_active_user,
                    active_user_percentage=active_user_percentage
                )
                db.add(daily_stat)
                logger.info(f"DAILY 통계 저장 완료: {today_date.strftime('%Y-%m-%d')}")

            db.commit()
            return {"status": "success", "recorded_at": dtNow.isoformat()}

    except Exception as e:
        logger.error(f"사용자 통계 생성 또는 DB 저장 중 오류 발생: {str(e)}", exc_info=True)
        raise


@celery.task(
    bind=True,
    name="stockeasy.workers.statistics.user_statistics_tasks.record_monthly_stats",
    queue="general-periodic",
    max_retries=3,
    soft_time_limit=600,
    time_limit=700,
    acks_late=True,
    reject_on_worker_lost=True
)
def record_monthly_stats(self):
    """
    매월 말일 자정에 실행되는 태스크.
    해당 월의 'DAILY' 통계들을 집계하여 'MONTHLY' 레코드로 저장합니다.
    """
    if settings.ENV == "development":
        logger.info("개발 환경에서는 월간 사용자 통계를 기록하지 않습니다.")
        return

    today = datetime.now().date()
    # 오늘이 해당 월의 마지막 날이 아니면 실행하지 않음
    last_day_of_month_num = calendar.monthrange(today.year, today.month)[1]
    if today.day != last_day_of_month_num:
        return

    # 통계 기간 설정 (해당 월 1일 ~ 말일)
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month + timedelta(days=last_day_of_month_num))

    logger.info(f"월간 사용자 통계 생성 시작: {start_of_month.strftime('%Y-%m')}")

    try:
        with SessionLocal() as db:
            # 1. 월간 통계 데이터 집계
            # 해당 월의 'DAILY' 통계 데이터를 조회
            daily_stats_query = db.query(UserStatistics).filter(
                UserStatistics.stat_type == 'DAILY',
                UserStatistics.report_at >= start_of_month,
                UserStatistics.report_at < end_of_month
            )

            # 집계: 신규 사용자 및 신규 채팅 세션은 'DAILY' 기록을 합산
            monthly_aggregates = daily_stats_query.with_entities(
                func.sum(UserStatistics.new_users).label('new_users_month'),
                func.sum(UserStatistics.new_chat_sessions).label('new_sessions_month')
            ).one()

            new_users_month = monthly_aggregates.new_users_month or 0
            new_sessions_month = monthly_aggregates.new_sessions_month or 0

            # 집계: 전체 사용자 및 전체 채팅 세션은 월말 'DAILY' 데이터 사용
            last_day_stat = daily_stats_query.order_by(UserStatistics.report_at.desc()).first()

            if last_day_stat:
                total_users = last_day_stat.total_users
                total_sessions = last_day_stat.total_chat_sessions
            else:
                # 해당 월에 일일 통계가 없는 경우, 직접 조회 (폴백 로직)
                logger.warning(f"{start_of_month.strftime('%Y-%m')}월의 DAILY 통계가 없어 직접 조회합니다.")
                total_users = get_total_users_sync(db)
                total_sessions = get_total_chat_sessions_sync(db).get('total', 0)

            # 월간 활성 사용자(unique)는 중복 계산을 피하기 위해 별도로 직접 조회
            active_users_month = get_active_users_sync(db, start_of_month, end_of_month).get('total', 0)

            logger.info(f"월간 DB 통계: 전체 사용자={total_users}, 활성={active_users_month}, "
                        f"신규={new_users_month}, 전체 세션={total_sessions}, 신규 세션={new_sessions_month}")

            # 2. 비율 계산
            sessions_per_user = (total_sessions / total_users) if total_users > 0 else 0
            sessions_per_active_user = (new_sessions_month / active_users_month) if active_users_month > 0 else 0
            active_user_percentage = (active_users_month / total_users) * 100 if total_users > 0 else 0

            # 3. 'MONTHLY' 통계 DB 저장
            monthly_stat = UserStatistics(
                stat_type='MONTHLY',
                report_at=datetime.combine(today, datetime.max.time()), # 월말일의 마지막 시간으로 기록
                total_users=total_users,
                new_users=new_users_month,
                active_users=active_users_month,
                total_chat_sessions=total_sessions,
                new_chat_sessions=new_sessions_month,
                sessions_per_user=sessions_per_user,
                sessions_per_active_user=sessions_per_active_user,
                active_user_percentage=active_user_percentage
            )
            db.add(monthly_stat)
            db.commit()
            logger.info(f"MONTHLY 통계 저장 완료: {start_of_month.strftime('%Y-%m')}")
            return {"status": "success", "month": start_of_month.strftime('%Y-%m')}

    except Exception as e:
        logger.error(f"월간 사용자 통계 생성 또는 DB 저장 중 오류 발생: {str(e)}", exc_info=True)
        raise


# --- 동기적 통계 조회 함수들 ---

def get_total_users_sync(db: Session):
    """전체 사용자 수를 조회합니다."""
    try:
        result = db.query(func.count(User.id)).scalar()
        return result or 0
    except Exception as e:
        logger.error(f"전체 사용자 수 조회 중 오류: {str(e)}")
        return 0

def get_active_users_sync(db: Session, start_time, end_time):
    """지정된 기간 동안 활동한 사용자 수를 조회합니다 (updated_at 기준)."""
    try:
        count = db.query(func.count(User.id))\
            .filter(User.updated_at >= start_time)\
            .filter(User.updated_at < end_time)\
            .scalar()
        return {"total": count or 0}
    except Exception as e:
        logger.error(f"기간 내 활동 사용자 수 조회 중 오류: {str(e)}")
        return {"total": 0}

def get_new_users_sync(db: Session, start_time, end_time):
    """지정된 기간 동안 새로 가입한 사용자 수를 조회합니다 (created_at 기준)."""
    try:
        count = db.query(func.count(User.id))\
            .filter(User.created_at >= start_time)\
            .filter(User.created_at < end_time)\
            .scalar()
        return {"total": count or 0}
    except Exception as e:
        logger.error(f"기간 내 신규 사용자 수 조회 중 오류: {str(e)}")
        return {"total": 0}

def get_total_chat_sessions_sync(db: Session):
    """전체 채팅 세션 수를 조회합니다."""
    try:
        count = db.query(func.count(StockChatSession.id)).scalar()
        return {"total": count or 0}
    except Exception as e:
        logger.error(f"전체 채팅 세션 수 조회 중 오류: {str(e)}")
        return {"total": 0}

def get_daily_chat_sessions_sync(db: Session, start_time, end_time):
    """지정된 기간 동안 생성된 채팅 세션 수를 조회합니다."""
    try:
        count = db.query(func.count(StockChatSession.id))\
            .filter(StockChatSession.created_at >= start_time)\
            .filter(StockChatSession.created_at < end_time)\
            .scalar()
        return {"total": count or 0}
    except Exception as e:
        logger.error(f"기간 내 채팅 세션 수 조회 중 오류: {str(e)}")
        return {"total": 0}