from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator, Generator, Optional
from common.core.config import settings
from contextlib import contextmanager
from loguru import logger

# PostgreSQL URL 생성
DATABASE_URL_SYNC = settings.DATABASE_URL
# 접속 드라이버만 변경
DATABASE_URL = DATABASE_URL_SYNC.replace('postgresql+psycopg2://', 'postgresql+asyncpg://')

# 엔진 생성
# PgBouncer 사용 여부 확인
using_pgbouncer = "pgbouncer" in settings.DATABASE_URL

# 기본 엔진 설정
engine_args = {
    "pool_pre_ping": True,
    "pool_use_lifo": True,     # 중요: LIFO 방식으로 유휴 연결 감소
}

# PgBouncer 사용 여부에 따른 풀 설정
if using_pgbouncer:
    # PgBouncer 사용 시 최소한의 풀링
    engine_args.update({
        "pool_size": 15,       # 5에서 15로 증가
        "max_overflow": 20,    # 5에서 20으로 증가  
        "pool_timeout": 30,    # 10에서 30으로 증가
        "pool_recycle": 300,
    })
else:
    # 직접 PostgreSQL 연결 시 원래 풀링 설정
    engine_args.update({
        "pool_size": 30,       # 20에서 30으로 증가
        "max_overflow": 30,    # 20에서 30으로 증가
        "pool_timeout": 45,    # 30에서 45로 증가
        "pool_recycle": 300,
    })
    # PostgreSQL 특화 설정은 PgBouncer 없을 때만
    engine_args["connect_args"] = {
        "options": "-c statement_timeout=30000 -c idle_in_transaction_session_timeout=300000"
    }

engine = create_engine(
    DATABASE_URL_SYNC,
    **engine_args
)

if using_pgbouncer:
    # PgBouncer 사용 시 최소한의 풀링
    pool_settings = {
        "pool_size": 35,       # 5에서 15로 증가
        "max_overflow": 40,    # 추가
        "pool_timeout": 30,    # 10에서 30으로 증가
        "pool_recycle": 300,
    }
else:
    # 직접 PostgreSQL 연결 시 원래 풀링 설정
    pool_settings = {
        "pool_size": 30,       # 20에서 30으로 증가
        "max_overflow": 30,    # 추가
        "pool_timeout": 45,    # 30에서 45로 증가
        "pool_recycle": 900,
    }

async_engine = create_async_engine(
    DATABASE_URL,
    # 기본 설정
    pool_pre_ping=True,  # 연결이 유효한지 확인
    pool_use_lifo=True,  # 마지막으로 사용된 연결을 재사용 (LIFO)
    
    # 풀 크기 설정 - 명시적으로 지정
    pool_size=pool_settings["pool_size"],
    max_overflow=pool_settings["max_overflow"],
    pool_timeout=pool_settings["pool_timeout"],
    pool_recycle=pool_settings["pool_recycle"],
    
    # 기타 설정
    echo=False,  # SQL 로깅 비활성화 (필요시 True로 변경)
    future=True,  # SQLAlchemy 2.0 호환성
)

logger.info(f"SQLAlchemy 연결 풀 설정 - 크기: {pool_settings['pool_size']}, "
           f"최대 오버플로우: {pool_settings['max_overflow']}, "
           f"타임아웃: {pool_settings['pool_timeout']}초, "
           f"재활용: {pool_settings['pool_recycle']}초")

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """데이터베이스 세션 생성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_db_async() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 의존성"""
    #try-finally를 쓸 필요 없음. async with 자체가 세션 정리
    async with AsyncSessionLocal() as session:
        yield session


async def get_db_session() -> AsyncSession:
    """
    비동기 DB 세션을 생성하여 반환합니다.
    멀티에이전트 시스템에서 세션 관리를 위한 용도로 사용됩니다.
    
    Returns:
        AsyncSession: 비동기 DB 세션
    """
    session = None
    try:
        session = AsyncSessionLocal()
        logger.debug("새 DB 세션 생성")
        return session
    except Exception as e:
        logger.error(f"DB 세션 생성 중 오류 발생: {e}")
        if session:
            try:
                await session.close()
            except Exception as close_error:
                logger.error(f"DB 세션 닫기 중 오류 발생: {close_error}")
        raise


async def close_db_connections() -> None:
    """
    애플리케이션 종료 시 DB 연결 정리
    
    모든 DB 연결을 안전하게 종료하는 함수입니다.
    애플리케이션 종료 시점에 호출해야 합니다.
    """
    logger.info("DB 연결 종료 중...")
    await async_engine.dispose()
    logger.info("DB 연결이 안전하게 종료되었습니다.")
