"""
PostgreSQL 유휴 세션 정리 스크립트
"""

import asyncio
import os
import sys
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 환경 변수 설정 - production 환경으로 명시적 설정
os.environ["ENV"] = "production"
os.environ["ENVIRONMENT"] = "production"

from dotenv import load_dotenv
# from common.core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
# from common.core.database import get_db_session
from datetime import timedelta

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()

# 데이터베이스 연결 정보를 직접 지정
DATABASE_URL = "postgresql+asyncpg://postgres:intellio@db:5432/intellio"

# 비동기 엔진 생성
async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_timeout=30,
    pool_recycle=1800   # 30분마다 연결 재사용 (세션 누적 방지)
)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

async def get_db_session_direct() -> AsyncSession:
    """
    비동기 DB 세션을 직접 생성하여 반환합니다.
    """
    session = AsyncSessionLocal()
    try:
        logger.debug("새 DB 세션 직접 생성")
        return session
    except Exception as e:
        logger.error(f"DB 세션 생성 중 오류 발생: {e}")
        await session.close()
        raise

async def clean_db_sessions():
    """
    데이터베이스에서 오래된 유휴 세션을 정리하는 함수
    
    정리 기준:
    - 상태가 'idle'인 세션
    - 일정 시간(기본값: 1분) 이상 유휴 상태인 세션
    """
    logger.info("유휴 DB 세션 정리 시작")
    
    try:
        # 데이터베이스 세션 직접 생성
        db_session: AsyncSession = await get_db_session_direct()
        
        # 1. 현재 유휴 세션 목록 조회
        idle_duration_limit = "1 minute"  # 1분 이상 유휴 상태인 세션 대상
        
        query = text("""
            SELECT pid, usename, application_name, client_addr, backend_start, 
                state, wait_event_type, wait_event, query, 
                now() - state_change AS idle_duration
            FROM pg_stat_activity 
            WHERE state = 'idle' AND (now() - state_change) > :idle_limit
            ORDER BY idle_duration DESC
        """)
        
        result = await db_session.execute(query, {"idle_limit": idle_duration_limit})
        idle_sessions = result.fetchall()
        
        logger.info(f"정리 대상 유휴 세션 수: {len(idle_sessions)}")
        
        # 2. 유휴 세션 종료
        for session in idle_sessions:
            pid = session.pid
            username = session.usename
            application = session.application_name
            idle_time = session.idle_duration
            
            # 데이터베이스 관리자 계정이나 시스템 세션은 제외
            if username in ["postgres", "rdsadmin"] or "autovacuum" in application:
                logger.debug(f"시스템 세션 제외 - PID: {pid}, 사용자: {username}, 앱: {application}")
                continue
                
            # 세션 종료
            terminate_query = text(f"SELECT pg_terminate_backend(:pid)")
            await db_session.execute(terminate_query, {"pid": pid})
            
            logger.info(f"세션 종료 - PID: {pid}, 사용자: {username}, 앱: {application}, 유휴 시간: {idle_time}")
        
        # 변경사항 커밋
        await db_session.commit()
        logger.info("유휴 DB 세션 정리 완료")
        
    except Exception as e:
        logger.error(f"세션 정리 중 오류 발생: {str(e)}")
    finally:
        # 세션 종료
        if 'db_session' in locals():
            await db_session.close()
        # 엔진 종료
        await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(clean_db_sessions()) 