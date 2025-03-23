"""의존성 주입 모듈

이 모듈은 FastAPI 엔드포인트에서 사용할 의존성들을 정의합니다.
주로 서비스 객체들의 인스턴스를 생성하고 관리합니다.
"""

from typing import Any, Generator
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.database import get_db, get_db_async
from stockeasy.services.telegram.rag import TelegramRAGService  # 지연 임포트
from stockeasy.services.rag_service import StockRAGService  # 싱글톤 RAG 서비스
from stockeasy.services.telegram.collector import CollectorService  # 지연 임포트
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from stockeasy.services.rag import StockeasyRAGService

async def get_telegram_rag_service() -> Any:
    """RAG 서비스 의존성
    
    텔레그램 메시지 검색과 요약을 위한 RAG 서비스를 제공합니다.
    """
    return TelegramRAGService()

def get_collector_service(
    db: Session = Depends(get_db)
) -> CollectorService:
    """Collector 서비스 의존성
    
    텔레그램 채널에서 메시지를 수집하는 서비스를 제공합니다.
    """
    return CollectorService(db=db)

def get_stockeasy_rag_service() -> StockeasyRAGService:
    """StockeasyRAG 서비스 의존성
    
    기본 RAG 서비스를 제공합니다.
    """
    return StockeasyRAGService()

def get_question_classifier() -> QuestionClassifierService:
    """질문 분류 서비스 의존성
    
    사용자 질문을 분류하는 서비스를 제공합니다.
    """
    return QuestionClassifierService()

async def get_stock_rag_service(
    db: AsyncSession = Depends(get_db_async)
) -> StockRAGService:
    """Stock RAG 서비스 의존성 (싱글톤)
    
    주식 분석을 위한 멀티에이전트 기반 RAG 서비스를 제공합니다.
    이 서비스는 싱글톤 패턴으로 구현되어 있어 항상 같은 인스턴스를 반환합니다.
    """
    return StockRAGService(db) 