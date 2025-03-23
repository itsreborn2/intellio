from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Cookie, status
from loguru import logger
from pydantic import BaseModel

from stockeasy.services.rag_service import StockRAGService
from stockeasy.services.rag import StockeasyRAGService
from stockeasy.services.telegram.rag import TelegramRAGService
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from stockeasy.api.deps import get_stockeasy_rag_service, get_stock_rag_service
from common.core.database import get_db_async
from sqlalchemy.ext.asyncio import AsyncSession

# FastAPI 라우터 설정 ( /api/v1/stockeasy/telegram)
router = APIRouter(prefix="", tags=["root"])

class UserQuestionRequest(BaseModel):
    question: str
    stock_code: str
    stock_name: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

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
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    authentication_required: bool = False

@router.post("/user_question", response_model=UserQuestionResponse)
async def user_question(
    request: UserQuestionRequest,
    db: AsyncSession = Depends(get_db_async),
    rag_stockeasy: StockeasyRAGService = Depends(get_stockeasy_rag_service),
    stock_rag_service: StockRAGService = Depends(get_stock_rag_service),
    authorization: Optional[str] = Header(None),
    session_cookie: Optional[str] = Cookie(None, alias="session_id")
) -> UserQuestionResponse:
    try:
        # 싱글톤 StockRAGService 인스턴스는 의존성에서 주입받음
        # session_id 우선순위:
        # 1. 요청 본문에 있는 session_id
        # 2. 쿠키에 있는 session_id
        # 3. 없으면 인증 오류 반환
        session_id = request.session_id or session_cookie
        
        # 세션 ID 없는 경우 인증 오류 반환
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="인증이 필요합니다. 로그인 후 이용해주세요."
            )
            
        # user_id 처리 (None이라도 명시적으로 전달)
        user_id = request.user_id
        
        # Authorization 헤더가 있으면 사용자 정보 추출 (사용자 정의 로직으로 대체해주세요)
        if authorization:
            # 토큰 파싱 및 검증 로직 (예시)
            # extracted_user_id = verify_token(authorization)
            # if extracted_user_id:
            #     user_id = extracted_user_id
            pass
        
        logger.info(f"질문 : {request.stock_name}({request.stock_code}), {request.question}, 세션: {session_id}, 사용자: {user_id or '익명'}")
        
        result = await stock_rag_service.analyze_stock(
            query=request.question,
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            session_id=session_id,
            user_id=user_id  # None이더라도 명시적으로 전달
        )
        
        # 인증 필요 확인
        if result.get("authentication_required", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.get("summary", "인증이 필요합니다. 로그인 후 이용해주세요.")
            )
        
        # 응답에 사용된 session_id와 user_id 포함
        actual_session_id = result.get("session_id") or session_id
        actual_user_id = result.get("user_id") or user_id
        
        # 결과에서 답변 추출
        answer = result.get('answer', '')
        return UserQuestionResponse(
            ok=True,
            status_message="답변 생성 성공",
            answer=answer,
            session_id=actual_session_id,
            user_id=actual_user_id,
            authentication_required=False
        )
        
    except HTTPException as he:
        # HTTP 예외는 그대로 다시 발생
        raise he
    except Exception as e:
        logger.error(f"질문 처리 중 오류가 발생했습니다: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"질문 처리 중 오류가 발생했습니다: {str(e)}"
        )

