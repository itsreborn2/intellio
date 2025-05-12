"""
일일 데이터 통계 처리 태스크

이 모듈은 매일 정해진 시간에 실행되어 하루 동안의 데이터를 수집하고 
통계를 생성하는 Celery 태스크를 포함합니다.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session  # 동기 세션 타입 추가

from common.core.config import settings
from common.core.database import AsyncSessionLocal, SessionLocal, get_db  # 동기 세션 팩토리와 get_db 추가
from common.models.user import User
from stockeasy.core.celery_app import celery
from stockeasy.models.chat import StockChatSession, StockChatMessage
from stockeasy.services.google_sheet_service import GoogleSheetService

logger = logging.getLogger(__name__)


@celery.task(
    bind=True,
    name="stockeasy.workers.statistics.daily_tasks.generate_daily_stats",
    queue="general-periodic",
    max_retries=3,
    soft_time_limit=600,
    time_limit=700,
    acks_late=True,
    reject_on_worker_lost=True
)
def generate_daily_stats(self):
    """
    매일 정해진 시간에 실행되는 태스크
    하루 동안의 데이터 통계를 생성하고 Google Sheets에 업데이트합니다.
    """
    # 개발환경에서는 기록하지 않음.
    if settings.ENV == "development":
        return
    # 10분마다 실행
    dtNow = datetime.now()
    if dtNow.minute < 50: # 50~59분에 실행하도록.
        return
    today_date = dtNow.date()
    report_date = today_date
    tommorow_date = today_date + timedelta(days=1)
    start_time = report_date
    end_time = tommorow_date

    print(f"일일 통계 생성 시작: {report_date}, {start_time}, {end_time}")

    try:
        # 동기 데이터베이스 세션 생성 및 통계 데이터 수집
        with SessionLocal() as db:
            logger.info("동기 세션으로 DB 통계 조회 시작")
            
            # 전체 사용자 수
            total_users = get_total_users_sync(db)
            
            # 일일 활성 사용자 수
            active_users_result = get_active_users_sync(db, start_time, end_time)
            active_users_today = active_users_result.get('total', 0)
            
            # 일일 신규 가입자 수
            new_users_result = get_new_users_sync(db, start_time, end_time)
            new_users_today = new_users_result.get('total', 0)
            
            # 전체 채팅 세션 수
            total_sessions_result = get_total_chat_sessions_sync(db)
            total_sessions = total_sessions_result.get('total', 0)
            
            # 오늘 생성된 채팅 세션 수
            daily_sessions_result = get_daily_chat_sessions_sync(db, start_time, end_time)
            new_sessions_today = daily_sessions_result.get('total', 0)
            
            logger.info(f"DB 통계 조회 결과: 전체 사용자={total_users}, 활성={active_users_today}, "
                      f"신규={new_users_today}, 전체 세션={total_sessions}, 신규 세션={new_sessions_today}")

        # 비율 계산 (0으로 나누기 방지)
        sessions_per_user_total = (total_sessions / total_users) if total_users > 0 else 0
        sessions_per_user_today = (new_sessions_today / active_users_today) if active_users_today > 0 else 0
        users_per_session_today = (active_users_today / total_users) if new_sessions_today > 0 else 0
        # Google Sheet에 기록할 데이터 행 준비
        # 컬럼 순서: 일자, 전체사용자, 신규사용자, 오늘사용자, 전체 채팅세션, 오늘 신규 채팅세션, 전체세션/전체사용자, 오늘세션/오늘사용자, 오늘사용자/전체사용자
        data_row = [
            dtNow.strftime('%Y-%m-%d %H:%M'),
            total_users,
            new_users_today,
            active_users_today,
            total_sessions,
            new_sessions_today,
            sessions_per_user_total, # float 형식으로 전송
            sessions_per_user_today,  # float 형식으로 전송
            users_per_session_today  # float 형식으로 전송
        ]

        logger.info(f"Google Sheet에 업데이트할 데이터: {data_row}")

        # 3. Google Sheets 업데이트
        # GoogleSheetService 인스턴스 생성 (환경 변수나 설정 파일에서 Credential 경로 로드)
        # GOOGLE_APPLICATION_CREDENTIALS와 GOOGLE_SHEET_ID가 settings에 정의되어 있다고 가정
        if not settings.GOOGLE_APPLICATION_CREDENTIALS:
             logger.error("Google Sheets API Credentials 경로 또는 Sheet ID가 설정되지 않았습니다.")
             raise ValueError("Google Sheets 설정이 누락되었습니다.")

        sheet_service = GoogleSheetService(credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS)
        sheet_url = "https://docs.google.com/spreadsheets/d/1AgbEpblhoqSBTmryDjSSraqc5lRdgWKNwBUA4VYk2P4/edit"
        
        # 기본 시트 업데이트
        worksheet_name = "사용자통계" # 대상 워크시트 이름
        worksheet = sheet_service.open_sheet_by_url(sheet_url, worksheet_name=worksheet_name)
        worksheet.append_row(data_row, value_input_option='USER_ENTERED')
        
        logger.info(f"{report_date} 기준 통계 Google Sheet 업데이트 완료 (워크시트: {worksheet_name})")
        
        # 23시 50분 이후에만 일별 통계시트에도 기록
        if dtNow.hour == 23 and dtNow.minute >= 50:
            # 일별 통계용 데이터 행 준비 (날짜 형식을 '년.월.일'로 변경)
            daily_data_row = data_row.copy()
            daily_data_row[0] = dtNow.strftime('%Y-%m-%d')  # 날짜 형식 변경
            
            # 일별 통계 시트 업데이트
            daily_worksheet_name = "사용자통계-일별"
            daily_worksheet = sheet_service.open_sheet_by_url(sheet_url, worksheet_name=daily_worksheet_name)
            daily_worksheet.append_row(daily_data_row, value_input_option='USER_ENTERED')
            
            logger.info(f"{report_date} 기준 일별 통계 Google Sheet 업데이트 완료 (워크시트: {daily_worksheet_name})")

        return {"status": "success", "date": report_date.isoformat(), "stats_written": data_row}

    except Exception as e:
        logger.error(f"일일 통계 생성 또는 Google Sheet 업데이트 중 오류 발생: {str(e)}", exc_info=True)
        # 실패 시 Celery 태스크 재시도 또는 오류 로깅 강화 가능
        raise


# 동기적 통계 조회 함수들
def get_total_users_sync(db: Session):
    """전체 사용자 수를 조회합니다."""
    try:
        result = db.query(func.count(User.id)).scalar()
        return result or 0
    except Exception as e:
        logger.error(f"전체 사용자 수 조회 중 오류: {str(e)}")
        return 0 # 오류 시 0 반환


def get_active_users_sync(db: Session, start_time, end_time):
    """지정된 기간 동안 활동한 사용자 수를 조회합니다 (updated_at 기준)."""
    try:
        count = db.query(func.count(User.id))\
            .filter(User.updated_at >= start_time)\
            .filter(User.updated_at < end_time)\
            .scalar() or 0
        logger.info(f"활성 사용자 통계 조회 결과: {count}")
        return {'total': count}
    except Exception as e:
        logger.error(f"활성 사용자 통계 조회 중 오류: {str(e)}")
        return {'total': 0, 'error': str(e)}


def get_new_users_sync(db: Session, start_time, end_time):
    """지정된 기간 동안 새로 가입한 사용자 수를 조회합니다 (created_at 기준)."""
    try:
        count = db.query(func.count(User.id))\
            .filter(User.created_at >= start_time)\
            .filter(User.created_at < end_time)\
            .scalar() or 0
        return {'total': count}
    except Exception as e:
        logger.error(f"신규 가입자 통계 조회 중 오류: {str(e)}")
        return {'total': 0, 'error': str(e)}


def get_total_chat_sessions_sync(db: Session):
    """전체 채팅 세션 수를 조회합니다."""
    try:
        count = db.query(func.count(StockChatSession.id)).scalar() or 0
        logger.info(f"전체 채팅 세션 통계 조회 결과: {count}")
        return {'total': count}
    except Exception as e:
        logger.error(f"전체 채팅 세션 수 조회 중 오류: {str(e)}")
        return {'total': 0, 'error': str(e)}


def get_daily_chat_sessions_sync(db: Session, start_time, end_time):
    """지정된 기간 동안 생성된 채팅 세션 수를 조회합니다."""
    try:
        count = db.query(func.count(StockChatSession.id))\
            .filter(StockChatSession.created_at >= start_time)\
            .filter(StockChatSession.created_at < end_time)\
            .scalar() or 0
        logger.info(f"일일 채팅 세션 통계 조회 결과: {count}")
        return {'total': count}
    except Exception as e:
        logger.error(f"일일 채팅 세션 통계 조회 중 오류: {str(e)}")
        return {'total': 0, 'error': str(e)}


# if __name__ == "__main__":
#     import logging
#     logging.basicConfig(level=logging.INFO) # 간단한 로깅 설정
#     logger.info("daily_tasks.py를 직접 실행하여 generate_daily_stats() 테스트 시작...")
#     try:
#         result = generate_daily_stats()
#         logger.info(f"generate_daily_stats() 실행 완료. 결과: {result}")
#     except Exception as e:
#         logger.error(f"generate_daily_stats() 실행 중 오류 발생: {e}", exc_info=True)
#     logger.info("generate_daily_stats() 테스트 종료.")