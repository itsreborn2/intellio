from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator, Generator
from common.core.config import settings

# PostgreSQL URL 생성
DATABASE_URL_SYNC = settings.DATABASE_URL
DATABASE_URL = DATABASE_URL_SYNC.replace('postgresql+psycopg2://', 'postgresql+asyncpg://')

# SQLAlchemy의 pool_size + max_overflow는 max_connections의 75% 이하로 설정하는 것이 안전. 기본값 100
# 엔진 생성
engine = create_engine(
    DATABASE_URL_SYNC,
    pool_pre_ping=True,
    echo=True,
    pool_size=30,
    max_overflow=45,
    pool_timeout=60
)

# 비동기 엔진 생성
async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=True,
    pool_size=30,
    max_overflow=50,
    pool_timeout=60
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

def get_db() -> Generator[Session, None, None]:
    """데이터베이스 세션 생성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_db_async() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 의존성"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# async def get_db_async() -> AsyncSession:
#     """비동기 데이터베이스 세션 생성"""
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#         finally:
#             await session.close()
