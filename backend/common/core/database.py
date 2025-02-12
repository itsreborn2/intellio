from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator, Generator
from common.core.config import settings
from contextlib import contextmanager

# PostgreSQL URL 생성
DATABASE_URL_SYNC = settings.DATABASE_URL
DATABASE_URL = DATABASE_URL_SYNC.replace('postgresql+psycopg2://', 'postgresql+asyncpg://')

# SQLAlchemy의 pool_size + max_overflow는 max_connections의 75% 이하로 설정하는 것이 안전. 기본값 100
# 엔진 생성
engine = create_engine(
    DATABASE_URL_SYNC,
    pool_pre_ping=True,
    #echo=True, # 쿼리 로깅
    pool_size=30,
    max_overflow=45,
    pool_timeout=30,
    pool_recycle=1800   # 30분마다 연결 재사용 (세션 누적 방지
)

# asyncpg는 자체 커넥션 풀을 사용하고, pool_size는 asyncpg.Pool과 충돌할 수 있음
# async_engine에서 커넥션 풀 관련 설정을 직접 관리하지 않는 것이 일반적인 권장사항
# max_overflow 옵션도 비동기 엔진에서는 무의미
# 비동기 엔진 생성
async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    #echo=True, # 쿼리 로깅
    #max_overflow=50,
    pool_timeout=30,
    pool_recycle=1800   # 30분마다 연결 재사용 (세션 누적 방지
)

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

# async def get_db_async() -> AsyncSession:
#     """비동기 데이터베이스 세션 생성"""
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#         finally:
#             await session.close()
