from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from backend.stockeasy.services.rag import StockeasyRAGService
from stockeasy.services.telegram.rag import TelegramRAGService
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from . import deps


# FastAPI 라우터 설정 ( /api/v1/stockeasy/telegram)
root_router = APIRouter(prefix="", tags=["root"])


class UserQuestionRequest(BaseModel):
    question: str

# 유저 질문의 응답용 모델
class Source(BaseModel):
    document_id: str
    title: str = None
    url: str = None
    content_snippet: str = None
    relevance_score: float = None

class UserQuestionResponse(BaseModel):
    answer: str
    sources: Optional[List[Source]] = None

@root_router.post("/user_question", response_model=UserQuestionResponse)
async def user_question(
    request: UserQuestionRequest,
    rag_stockeasy: StockeasyRAGService = Depends(deps.get_stockeasy_rag_service),
    
) -> UserQuestionResponse:
    try:
        answer = await rag_stockeasy.user_question(request.question)
        
        logger.info(f"==== 답변 생성 결과 ====")
        logger.info(f"답변: {answer}")
        # 4. 응답 반환
        return UserQuestionResponse(
            answer=answer
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"질문 처리 중 오류가 발생했습니다: {str(e)}"
        )

