"""의존성 주입 모듈

이 모듈은 FastAPI 엔드포인트에서 사용할 의존성들을 정의합니다.
주로 서비스 객체들의 인스턴스를 생성하고 관리합니다.
"""

from typing import Any, Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.telegram.rag import RAGService  # 지연 임포트
from app.services.telegram.collector import CollectorService  # 지연 임포트

def get_db() -> Generator[Session, None, None]:
    """데이터베이스 세션을 제공합니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_rag_service() -> Any:
    """RAG 서비스 의존성
    
    텔레그램 메시지 검색과 요약을 위한 RAG 서비스를 제공합니다.
    """
    return RAGService()

def get_collector_service(
    db: Session = Depends(get_db)
) -> CollectorService:
    """Collector 서비스 의존성
    
    텔레그램 채널에서 메시지를 수집하는 서비스를 제공합니다.
    """
    return CollectorService(db=db)
