"""
TimescaleDB 데이터베이스 연결 관리
"""
import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import text
from loguru import logger

from .config import get_settings


# 설정 로드
settings = get_settings()

# TimescaleDB 전용 동기 엔진
timescale_sync_engine = create_engine(
    settings.TIMESCALE_DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,  # 1시간
    pool_pre_ping=True,
    echo=False
)

# TimescaleDB 전용 비동기 엔진
timescale_async_engine = create_async_engine(
    settings.TIMESCALE_ASYNC_DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,  # 1시간
    pool_pre_ping=True,
    pool_use_lifo=True,  # LIFO 방식으로 유휴 연결 감소
    echo=False,
    future=True  # SQLAlchemy 2.0 호환성
)

# TimescaleDB 전용 세션 팩토리들
TimescaleSessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=timescale_sync_engine
)

TimescaleAsyncSessionLocal = async_sessionmaker(
    timescale_async_engine, 
    expire_on_commit=False,
    class_=AsyncSession
)

logger.info(f"TimescaleDB 연결 풀 설정 - 크기: 20, 최대 오버플로우: 30, 타임아웃: 30초, 재활용: 3600초")


async def get_timescale_session() -> AsyncGenerator[AsyncSession, None]:
    """
    TimescaleDB 비동기 세션 생성 (FastAPI 의존성 주입용)
    
    Usage:
        @app.get("/api/data")
        async def get_data(session: AsyncSession = Depends(get_timescale_session)):
            # 세션 사용
            pass
    
    Yields:
        AsyncSession: TimescaleDB 비동기 세션
    """
    async with TimescaleAsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"TimescaleDB 세션 오류: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_timescale_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    TimescaleDB 비동기 세션 컨텍스트 매니저
    
    Usage:
        async with get_timescale_session_context() as session:
            # 세션 사용
            result = await session.execute(query)
    
    Yields:
        AsyncSession: TimescaleDB 비동기 세션
    """
    session = TimescaleAsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        logger.error(f"TimescaleDB 세션 컨텍스트 오류: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()


def get_timescale_sync_session() -> Session:
    """
    TimescaleDB 동기 세션 생성 (동기 코드용)
    
    주의: 세션 사용 후 반드시 close() 호출 필요
    
    Returns:
        Session: TimescaleDB 동기 세션
    """
    return TimescaleSessionLocal()


async def create_timescale_session() -> AsyncSession:
    """
    TimescaleDB 비동기 세션을 직접 생성하여 반환
    
    주의: 세션 사용 후 반드시 close() 호출 필요
    
    Returns:
        AsyncSession: TimescaleDB 비동기 세션
    """
    try:
        session = TimescaleAsyncSessionLocal()
        logger.debug("새 TimescaleDB 세션 생성")
        return session
    except Exception as e:
        logger.error(f"TimescaleDB 세션 생성 중 오류 발생: {e}")
        raise


async def test_timescale_connection() -> bool:
    """
    TimescaleDB 연결 테스트
    
    Returns:
        bool: 연결 성공 여부
    """
    try:
        async with get_timescale_session_context() as session:
            result = await session.execute(text("SELECT version();"))
            version = result.scalar()
            logger.info(f"TimescaleDB 연결 성공: {version}")
            
            # TimescaleDB 확장 확인
            result = await session.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';")
            )
            extension_info = result.fetchone()
            
            if extension_info:
                logger.info(f"TimescaleDB 확장 확인: {extension_info[0]} v{extension_info[1]}")
                return True
            else:
                logger.warning("TimescaleDB 확장이 설치되지 않았습니다")
                return False
                
    except Exception as e:
        logger.error(f"TimescaleDB 연결 테스트 실패: {e}")
        return False


async def close_timescale_connections() -> None:
    """
    애플리케이션 종료 시 TimescaleDB 연결 정리
    
    모든 TimescaleDB 연결을 안전하게 종료하는 함수입니다.
    애플리케이션 종료 시점에 호출해야 합니다.
    """
    logger.info("TimescaleDB 연결 종료 중...")
    
    try:
        # 비동기 엔진 종료
        await timescale_async_engine.dispose()
        logger.info("TimescaleDB 비동기 엔진이 안전하게 종료되었습니다")
        
        # 동기 엔진 종료 (비동기 컨텍스트에서는 스레드 풀에서 실행)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, timescale_sync_engine.dispose)
        logger.info("TimescaleDB 동기 엔진이 안전하게 종료되었습니다")
        
    except Exception as e:
        logger.error(f"TimescaleDB 연결 종료 중 오류: {e}")


# 연결 상태 모니터링용
class TimescaleConnectionMonitor:
    """TimescaleDB 연결 상태 모니터링"""
    
    @staticmethod
    async def get_connection_info() -> dict:
        """현재 연결 상태 정보 조회"""
        try:
            async with get_timescale_session_context() as session:
                # 활성 연결 수 조회
                result = await session.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = :datname"),
                    {"datname": settings.TIMESCALE_DB}
                )
                active_connections = result.scalar()
                
                # 데이터베이스 크기 조회
                result = await session.execute(
                    text("SELECT pg_size_pretty(pg_database_size(:datname))"),
                    {"datname": settings.TIMESCALE_DB}
                )
                db_size = result.scalar()
                
                return {
                    "status": "healthy",
                    "active_connections": active_connections,
                    "database_size": db_size,
                    "pool_size": timescale_async_engine.pool.size(),
                    "checked_out_connections": timescale_async_engine.pool.checkedout(),
                }
                
        except Exception as e:
            logger.error(f"TimescaleDB 연결 정보 조회 실패: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            } 