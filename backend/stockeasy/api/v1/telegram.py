"""텔레그램 메시지 요약 API 라우터

이 모듈은 텔레그램 메시지를 검색하고 요약하는 API 엔드포인트를 제공합니다.
주요 기능:
1. 텔레그램 메시지 수집 (Telethon 사용)
2. 텔레그램 메시지 검색 (Pinecone 벡터 DB 사용)
3. 검색된 메시지 요약 (LangChain 사용)
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from stockeasy.services.telegram.question_classifier import QuestionClassification, QuestionClassifierService
from stockeasy.services.telegram.rag import TelegramRAGService
from stockeasy.services.telegram.collector import CollectorService
from stockeasy.api import deps
from pydantic import BaseModel

# FastAPI 라우터 설정 ( /api/v1/stockeasy/telegram)
telegram_router = APIRouter(prefix="/telegram", tags=["telegram"])

class SummarizeRequest(BaseModel):
    """요약 요청 스키마
    
    Attributes:
        query (str): 사용자의 질문 또는 요약 요청
        k (int): 검색할 관련 메시지 수. 기본값은 5개
    """
    query: str
    k: int = 5

class SummarizeResponse(BaseModel):
    """요약 응답 스키마
    
    Attributes:
        summary (str): 메시지들의 요약 내용
        related_messages (List[str]): 요약에 사용된 관련 메시지들
    """
    summary: str
    related_messages: List[str]

class CollectRequest(BaseModel):
    """메시지 수집 요청 스키마
    
    Attributes:
        channel_id (str): 텔레그램 채널 ID
        limit (int): 수집할 최대 메시지 수. 기본값은 100개
    """
    channel_id: str
    limit: int = 100

class CollectResponse(BaseModel):
    """메시지 수집 응답 스키마
    
    Attributes:
        messages (List[Dict[str, Any]]): 수집된 메시지 목록
        count (int): 수집된 메시지 개수
    """
    messages: List[Dict[str, Any]]
    count: int

@telegram_router.post("/summarize", response_model=SummarizeResponse)
async def summarize_messages(
    request: SummarizeRequest,
    
    rag_service: TelegramRAGService = Depends(deps.get_telegram_rag_service)
) -> SummarizeResponse:
    """텔레그램 메시지를 검색하고 요약하는 엔드포인트
    
    Args:
        request (SummarizeRequest): 요약 요청 정보
        rag_service (RAGService): RAG 서비스 인스턴스
        
    Returns:
        SummarizeResponse: 요약된 내용과 관련 메시지들
        
    Example:
        요청 예시:
        ```
        POST /api/v1/telegram/summarize
        {
            "query": "최근 코스피 동향은?",
            "k": 5
        }
        ```
        
        응답 예시:
        ```
        {
            "summary": "최근 코스피는 상승세를 보이고 있으며...",
            "related_messages": [
                "코스피 2,800선 돌파...",
                "외국인 매수세 지속..."
            ]
        }
        ```
    """
    qc = QuestionClassifierService()
    classification:QuestionClassification = qc.classify_question(request.query)
        
    # 1. 벡터 DB에서 관련 메시지 검색
    messages = await rag_service.search_messages(request.query, classification)
    
    # 2. 검색된 메시지들을 요약
    summary = await rag_service.summarize(messages, classification)
    
    # 3. 응답 반환
    return SummarizeResponse(
        summary=summary,
        related_messages=messages
    )

