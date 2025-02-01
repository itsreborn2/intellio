from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,    # 연결 확인
    pool_size=20,          # 기본 20개 (여유있게 설정)
    max_overflow=30,       # 최대 50개까지 가능
    pool_timeout=30,       # 커넥션 대기 시간
    echo=False            # 프로덕션에서는 SQL 로깅 비활성화
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """데이터베이스 세션을 제공하는 의존성 주입 함수"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
