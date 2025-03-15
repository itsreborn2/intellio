from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from stockeasy.services.rag import StockeasyRAGService
from stockeasy.services.telegram.rag import TelegramRAGService
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from stockeasy.api.deps import get_stockeasy_rag_service

# FastAPI 라우터 설정 ( /api/v1/stockeasy/telegram)
router = APIRouter(prefix="", tags=["root"])



class UserQuestionRequest(BaseModel):
    question: str
    stock_code:str
    stock_name:str

# 유저 질문의 응답용 모델
class Source(BaseModel):
    document_id: str
    title: str = None
    url: str = None
    content_snippet: str = None
    relevance_score: float = None

class BaseResponse(BaseModel):
    ok: bool
    status_message: str

class UserQuestionResponse(BaseResponse):
    answer: str
    sources: Optional[List[Source]] = None

@router.post("/user_question", response_model=UserQuestionResponse)
async def user_question(
    request: UserQuestionRequest,
    rag_stockeasy: StockeasyRAGService = Depends(get_stockeasy_rag_service),
    
) -> UserQuestionResponse:
    try:
        logger.info("==== 답변 생성 시작 ====")
        answer = await rag_stockeasy.user_question(request.stock_code, request.stock_name, request.question)
        
        logger.info("==== 답변 생성 결과 ====")
        logger.info(f"답변: {answer}")
        # 4. 응답 반환
        return UserQuestionResponse(
            ok=True,
            status_message="답변 생성 성공",
            answer=answer
        )
        
    except Exception as e:
        logger.error(f"질문 처리 중 오류가 발생했습니다: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"질문 처리 중 오류가 발생했습니다: {str(e)}"
        )

