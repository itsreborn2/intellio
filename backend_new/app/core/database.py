from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models.base import Base

# PostgreSQL URL 생성
DATABASE_URL = "postgresql+asyncpg://intellio_user:intellio123@localhost:5432/intellio"
DATABASE_URL_SYNC = settings.DATABASE_URL

# 엔진 생성
engine = create_engine(
    DATABASE_URL_SYNC,
    pool_pre_ping=True,
    echo=True
)

# 비동기 엔진 생성
async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=True
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

def get_db() -> Session:
    """데이터베이스 세션 생성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_session() -> AsyncSession:
    """비동기 데이터베이스 세션 생성"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
