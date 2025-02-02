import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import text
from app.core.database import engine
from app.models.base import Base
from app.models import project, document  # 모든 모델 임포트

def init_db():
    """데이터베이스 테이블 초기화"""
    # 기존 테이블 삭제
    Base.metadata.drop_all(bind=engine)
    
    # 새로운 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    print("Database tables have been initialized.")

if __name__ == "__main__":
    init_db()
