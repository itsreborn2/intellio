"""
데이터 마이그레이션 스크립트

CSV에 저장된 '시간별 누적' 사용자 통계 데이터를 user_statistics 테이블로 이전합니다.
이 스크립트는 CSV의 원본 데이터를 기반으로 HOURLY, DAILY, MONTHLY 통계를 생성합니다.

- HOURLY: CSV의 시간별 데이터를 그대로 사용하고 비율을 재계산합니다.
- DAILY: 각 날짜의 마지막 시간대(23시) HOURLY 데이터를 그날의 최종 통계로 사용합니다.
- MONTHLY: 생성된 DAILY 데이터를 월별로 집계하여 생성합니다.

실행 방법 (backend 폴더에서):
docker-compose exec -w /backend celery-stockeasy python -m scripts.migrate_stats_from_csv
"""
import os
import sys
import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import text

# --- 프로젝트 경로 설정 ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from common.core.database import get_db
from stockeasy.models.user_statistics import UserStatistics

# --- 설정 ---
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), 'data', '스탁이지-섹터,통계 - 사용자통계.csv')

def load_and_clean_hourly_data(file_path: str) -> pd.DataFrame:
    """CSV에서 시간별 누적 데이터를 로드하고 정제합니다."""
    if not os.path.exists(file_path):
        logger.error(f"오류: CSV 파일을 찾을 수 없습니다. 경로: {file_path}")
        sys.exit(1)

    # 1. 최소한의 옵션으로 CSV를 읽어 파싱 오류를 방지합니다.
    #    - header=0: 첫 번째 줄을 헤더로 명시적으로 지정합니다.
    #    - encoding='utf-8-sig': BOM이 포함된 파일을 처리합니다.
    #    - index_col=False: 첫 번째 열을 인덱스로 사용하지 않도록 명시하여 컬럼 밀림 현상을 방지합니다.
    df = pd.read_csv(file_path, encoding='utf-8-sig', header=0, index_col=False)

    # 2. 필요한 컬럼명과 DB 필드명을 매핑합니다.
    column_mapping = {
        '일자': 'report_at', '전체사용자': 'total_users', '신규사용자': 'new_users',
        '오늘사용자': 'active_users', '전체 채팅세션': 'total_chat_sessions',
        '오늘 신규 채팅세션': 'new_chat_sessions'
    }
    required_csv_columns = list(column_mapping.keys())

    # 3. 필요한 컬럼만 선택하고 이름을 변경합니다.
    df = df[required_csv_columns].copy()
    df.rename(columns=column_mapping, inplace=True)

    # 4. 데이터 타입을 안전하게 변환합니다.
    #    - format을 지정하지 않아도 다양한 표준 날짜 형식을 자동으로 파싱합니다.
    df['report_at'] = pd.to_datetime(df['report_at'], errors='coerce')
    df.dropna(subset=['report_at'], inplace=True) # 날짜 변환 실패한 행 제거

    numeric_cols = ['total_users', 'new_users', 'active_users', 'total_chat_sessions', 'new_chat_sessions']
    for col in numeric_cols:
        # 쉼표(,)를 제거하고 숫자로 변환합니다.
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '', regex=False), errors='coerce')

    # 5. 최종 데이터 정제
    df.fillna(0, inplace=True)
    df.drop_duplicates(subset=['report_at'], keep='last', inplace=True)
    df.sort_values('report_at', inplace=True)

    logger.info(f"성공: {len(df)}개의 정제된 시간별 데이터를 CSV에서 로드했습니다.")
    return df

def calculate_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """통계 데이터프레임의 비율 컬럼들을 계산합니다."""
    df['sessions_per_user'] = (df['total_chat_sessions'] / df['total_users']).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    df['sessions_per_active_user'] = (df['new_chat_sessions'] / df['active_users']).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    df['active_user_percentage'] = (df['active_users'] / df['total_users']).replace([np.inf, -np.inf], 0).fillna(0).round(3)
    return df

def migrate_stats():
    """CSV 데이터를 로드하여 HOURLY, DAILY, MONTHLY 통계를 생성하고 DB에 저장합니다."""
    logger.info("데이터 마이그레이션을 시작합니다...")

    try:
        # 1. CSV에서 시간별(HOURLY) 원본 데이터 로드
        hourly_df = load_and_clean_hourly_data(CSV_FILE_PATH)
        hourly_df = calculate_ratios(hourly_df)
        hourly_df['stat_type'] = 'HOURLY'
        logger.info(f"HOURLY 데이터 생성 완료. 행 수: {len(hourly_df)}")

        # 2. HOURLY 데이터를 기반으로 DAILY 데이터 생성
        # 각 날짜의 마지막 시간대 데이터를 일일 최종 데이터로 사용
        daily_df = hourly_df.loc[hourly_df.groupby(hourly_df['report_at'].dt.date)['report_at'].idxmax()].copy()
        daily_df['stat_type'] = 'DAILY'
        # report_at을 23:59:59로 통일
        daily_df['report_at'] = daily_df['report_at'].apply(lambda dt: dt.replace(hour=23, minute=59, second=59))
        logger.info(f"DAILY 데이터 생성 완료. 행 수: {len(daily_df)}")

        # 3. DAILY 데이터를 기반으로 MONTHLY 데이터 생성
        monthly_df = daily_df.copy()
        monthly_df['month'] = monthly_df['report_at'].dt.to_period('M')

        # 월별 집계
        monthly_agg = monthly_df.groupby('month').agg(
            new_users=('new_users', 'sum'),
            new_chat_sessions=('new_chat_sessions', 'sum'),
            active_users=('active_users', 'mean'), # 월간 활성 유저는 일간 활성 유저의 평균으로 근사
            total_users=('total_users', 'last'),
            total_chat_sessions=('total_chat_sessions', 'last'),
            report_at=('report_at', 'last') # 월의 마지막 날짜를 기준으로 사용
        ).reset_index()

        monthly_agg['active_users'] = monthly_agg['active_users'].astype(int)
        monthly_agg['stat_type'] = 'MONTHLY'
        monthly_agg = calculate_ratios(monthly_agg)
        monthly_agg = monthly_agg.drop(columns=['month'])
        logger.info(f"MONTHLY 데이터 생성 완료. 행 수: {len(monthly_agg)}")

        # 4. 모든 데이터 통합 및 DB 저장
        final_df = pd.concat([hourly_df, daily_df, monthly_agg], ignore_index=True)
        # 최종 컬럼 순서 정리
        final_df = final_df[['stat_type', 'report_at', 'total_users', 'new_users', 'active_users', 'total_chat_sessions', 'new_chat_sessions', 'sessions_per_user', 'sessions_per_active_user', 'active_user_percentage']]

        with get_db() as db_session:
            logger.info("기존 user_statistics 테이블 데이터 삭제 중...")
            db_session.execute(text("TRUNCATE TABLE stockeasy.user_statistics"))

            logger.info(f"총 {len(final_df)}개의 통계 데이터를 DB에 삽입합니다.")
            records = final_df.to_dict(orient="records")
            db_session.bulk_insert_mappings(UserStatistics, records)
            db_session.commit()

        logger.info("데이터 마이그레이션 성공!")

    except Exception as e:
        logger.error(f"데이터 마이그레이션 중 오류 발생: {e}", exc_info=True)

if __name__ == "__main__":
    migrate_stats()
