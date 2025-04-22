"""
일일 데이터 통계 처리 태스크

이 모듈은 매일 정해진 시간에 실행되어 하루 동안의 데이터를 수집하고 
통계를 생성하는 Celery 태스크를 포함합니다.
"""
import logging
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.config import settings
from common.core.database import AsyncSessionLocal
from common.models.user import User, Session
from stockeasy.models.chat import StockChatSession, StockChatMessage
from stockeasy.services.google_sheet_service import GoogleSheetService

logger = logging.getLogger(__name__)


@shared_task
def generate_daily_stats():
    """
    매일 23시 55분에 실행되는 태스크
    하루 동안의 데이터 통계를 생성하고 Google Sheets에 업데이트합니다.
    """
    today_date = datetime.now().date()
    report_date = today_date# 통계 대상 날짜 (어제)
    tommorow_date = today_date + timedelta(days=1)
    start_time = report_date
    end_time = tommorow_date

    logger.info(f"일일 통계 생성 시작: {report_date}, {start_time}, {end_time}")

    try:
        # 1. 비동기 통계 데이터 수집 실행
        stats = run_async_stats(start_time, end_time)
        logger.info(f"일일 통계 DB 조회 결과: {stats}")

        # 2. 통계 데이터 가공 및 계산
        total_users = stats.get('total_users', 0)
        new_users_today = stats.get('new_users', {}).get('total', 0)
        active_users_today = stats.get('active_users', {}).get('total', 0)
        total_sessions = stats.get('total_chat_sessions',  {}).get('total', 0)
        new_sessions_today = stats.get('daily_chat_sessions', {}).get('total', 0)

        # 비율 계산 (0으로 나누기 방지)
        sessions_per_user_total = (total_sessions / total_users) if total_users > 0 else 0
        sessions_per_user_today = (new_sessions_today / active_users_today) if active_users_today > 0 else 0

        # Google Sheet에 기록할 데이터 행 준비
        # 컬럼 순서: 일자, 전체사용자, 신규사용자, 오늘사용자, 전체 채팅세션, 오늘 신규 채팅세션, 전체세션/전체사용자, 오늘세션/오늘사용자
        data_row = [
            report_date.strftime('%Y-%m-%d'),
            total_users,
            new_users_today,
            active_users_today,
            total_sessions,
            new_sessions_today,
            sessions_per_user_total, # float 형식으로 전송
            sessions_per_user_today  # float 형식으로 전송
        ]

        logger.info(f"Google Sheet에 업데이트할 데이터: {data_row}")

        # 3. Google Sheets 업데이트
        # GoogleSheetService 인스턴스 생성 (환경 변수나 설정 파일에서 Credential 경로 로드)
        # GOOGLE_APPLICATION_CREDENTIALS와 GOOGLE_SHEET_ID가 settings에 정의되어 있다고 가정
        if not settings.GOOGLE_APPLICATION_CREDENTIALS:
             logger.error("Google Sheets API Credentials 경로 또는 Sheet ID가 설정되지 않았습니다.")
             raise ValueError("Google Sheets 설정이 누락되었습니다.")

        sheet_service = GoogleSheetService(credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS)
        worksheet_name = "사용자통계" # 대상 워크시트 이름
        sheet_url = "https://docs.google.com/spreadsheets/d/1AgbEpblhoqSBTmryDjSSraqc5lRdgWKNwBUA4VYk2P4/edit"
        worksheet = sheet_service.open_sheet_by_url(sheet_url, worksheet_name=worksheet_name)
        worksheet.append_row(data_row, value_input_option='USER_ENTERED')
        # Google Sheet에 행 추가
        # sheet_service.append_row(
        #     spreadsheet_id=settings.GOOGLE_SHEET_ID,
        #     worksheet_name=worksheet_name,
        #     values=[data_row] # append_row는 값의 리스트를 받음
        # )

        logger.info(f"{report_date} 기준 통계 Google Sheet 업데이트 완료 (워크시트: {worksheet_name})")

        return {"status": "success", "date": report_date.isoformat(), "stats_written": data_row}

    except Exception as e:
        logger.error(f"일일 통계 생성 또는 Google Sheet 업데이트 중 오류 발생: {str(e)}", exc_info=True)
        # 실패 시 Celery 태스크 재시도 또는 오류 로깅 강화 가능
        raise


def run_async_stats(start_time, end_time):
    """
    비동기 데이터베이스 쿼리를 실행하여 필요한 모든 통계 데이터를 수집합니다.
    """
    import asyncio

    async def _collect_stats():
        async with AsyncSessionLocal() as db:
            stats = {}

            # 전체 사용자 수
            stats['total_users'] = await get_total_users(db)

            # 일일 활성 사용자 수
            stats['active_users'] = await get_active_users(db, start_time, end_time)

            # 일일 신규 가입자 수
            stats['new_users'] = await get_new_users(db, start_time, end_time)

            # 전체 채팅 세션 수
            stats['total_chat_sessions'] = await get_total_chat_sessions(db)

            # 오늘 생성된 채팅 세션 수
            stats['daily_chat_sessions'] = await get_daily_chat_sessions(db, start_time, end_time)

            # 필요시 전송된 메시지 수도 추가 가능
            # stats['messages'] = await get_messages(db, start_time, end_time)

            return stats

    # 비동기 함수를 동기적으로 실행
    return asyncio.run(_collect_stats())


async def get_total_users(db: AsyncSession):
    """전체 사용자 수를 조회합니다."""
    try:
        result = await db.execute(select(func.count(User.id)))
        return result.scalar_one_or_none() or 0
    except Exception as e:
        logger.error(f"전체 사용자 수 조회 중 오류: {str(e)}")
        return 0 # 오류 시 0 반환


async def get_active_users(db: AsyncSession, start_time, end_time):
    """지정된 기간 동안 활동한 사용자 수를 조회합니다 (updated_at 기준)."""
    try:
        result = await db.execute(
            select(func.count(User.id))
            .where(and_(
                User.updated_at >= start_time,
                User.updated_at < end_time
            ))
        )
        count = result.scalar_one_or_none() or 0
        logger.info(f"활성 사용자 통계 조회 결과: {count}")
        return {'total': count}
    except Exception as e:
        logger.error(f"활성 사용자 통계 조회 중 오류: {str(e)}")
        return {'total': 0, 'error': str(e)}


async def get_new_users(db: AsyncSession, start_time, end_time):
    """지정된 기간 동안 새로 가입한 사용자 수를 조회합니다 (created_at 기준)."""
    try:
        result = await db.execute(
            select(func.count(User.id))
            .where(and_(
                User.created_at >= start_time,
                User.created_at < end_time
            ))
        )
        count = result.scalar_one_or_none() or 0
        return {'total': count}
    except Exception as e:
        logger.error(f"신규 가입자 통계 조회 중 오류: {str(e)}")
        return {'total': 0, 'error': str(e)}


async def get_total_chat_sessions(db: AsyncSession):
    """전체 채팅 세션 수를 조회합니다."""
    try:
        result = await db.execute(select(func.count(StockChatSession.id)))
        count = result.scalar_one_or_none() or 0
        logger.info(f"전체 채팅 세션 통계 조회 결과: {count}")
        return {'total': count}
    except Exception as e:
        logger.error(f"전체 채팅 세션 수 조회 중 오류: {str(e)}")
        return 0 # 오류 시 0 반환


async def get_daily_chat_sessions(db: AsyncSession, start_time, end_time):
    """지정된 기간 동안 생성된 채팅 세션 수를 조회합니다."""
    try:
        result = await db.execute(
            select(func.count(StockChatSession.id))
            .where(and_(
                StockChatSession.created_at >= start_time,
                StockChatSession.created_at < end_time
            ))
        )
        count = result.scalar_one_or_none() or 0
        logger.info(f"일일 채팅 세션 통계 조회 결과: {count}")
        return {'total': count}
    except Exception as e:
        logger.error(f"일일 채팅 세션 통계 조회 중 오류: {str(e)}")
        return {'total': 0, 'error': str(e)}


# 메시지 통계 함수는 현재 최종 결과에 사용되지 않으므로 주석 처리하거나 필요시 활성화
# async def get_messages(db: AsyncSession, start_time, end_time):
#     """지정된 기간 동안 전송된 메시지 수를 조회합니다."""
#     try:
#         result = await db.execute(
#             select(func.count(StockChatMessage.id)) # 모델 이름 확인 필요
#             .where(and_(
#                 StockChatMessage.created_at >= start_time,
#                 StockChatMessage.created_at < end_time
#             ))
#         )
#         count = result.scalar_one_or_none() or 0
#         return {'total': count}
#     except Exception as e:
#         logger.error(f"메시지 통계 조회 중 오류: {str(e)}")
#         return {'total': 0, 'error': str(e)} 


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