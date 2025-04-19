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
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 10,
        "pool_recycle": 300,
    })
else:
    # 직접 PostgreSQL 연결 시 원래 풀링 설정
    engine_args.update({
        "pool_size": 20,
        "max_overflow": 20,
        "pool_timeout": 30,
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
        "pool_size": 5,
        "pool_timeout": 10,
        "pool_recycle": 300,
    }
else:
    # 직접 PostgreSQL 연결 시 원래 풀링 설정
    pool_settings = {
        "pool_size": 20,
        "pool_timeout": 30,
        "pool_recycle": 900,
    }

async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_use_lifo=True,
    **pool_settings,
    # 나머지 설정들...
)

# # asyncpg는 자체 커넥션 풀을 사용하고, pool_size는 asyncpg.Pool과 충돌할 수 있음
# # async_engine에서 커넥션 풀 관련 설정을 직접 관리하지 않는 것이 일반적인 권장사항
# # max_overflow 옵션도 비동기 엔진에서는 무의미
# # 비동기 엔진 생성
# # async_engine = create_async_engine(
# #     DATABASE_URL,
# #     pool_pre_ping=True,
# #     #echo=True, # 쿼리 로깅
# #     #max_overflow=50,
# #     pool_timeout=30,
# #     pool_recycle=60   # 30분마다 연결 재사용 (세션 누적 방지
# # )


# async_engine = create_async_engine(
#     DATABASE_URL,
#     pool_pre_ping=True,
#     #pool_size=20,
#     #pool_timeout=30,
#     #pool_recycle=900,       # 15분
#     pool_use_lifo=True, 
#     # asyncpg 특화 설정, pgboucer 안쓸땜.ㄴ
#     # connect_args={
#     #     "command_timeout": 60.0,                     # 쿼리 실행 타임아웃 (초)
#     #     "statement_cache_size": 100,                 # 성능 최적화
#     #     "server_settings": {
#     #         "idle_in_transaction_session_timeout": "600000",  # 10분(ms)
#     #         "idle_session_timeout": "300000"                 # 5분(ms)
#     #     }
#     # }
# )

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
    session = AsyncSessionLocal()
    try:
        logger.debug("새 DB 세션 생성")
        return session
    except Exception as e:
        logger.error(f"DB 세션 생성 중 오류 발생: {e}")
        await session.close()
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
