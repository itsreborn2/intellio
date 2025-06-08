"""
스탁이지 통계 API 라우터.

이 모듈은 스탁이지 DB의 통계 데이터를 제공하는 API 엔드포인트를 제공합니다.
"""
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel, Field
from loguru import logger

from common.core.database import get_db_async
from stockeasy.models.chat import StockChatSession
from common.core.deps import get_current_session
from common.models.user import Session

# 통계 라우터 정의
stats_router = APIRouter(prefix="/stats", tags=["통계"])

class BaseResponse(BaseModel):
    """기본 응답 모델"""
    ok: bool
    status_message: str

class StockPopularityItem(BaseModel):
    """인기 종목 항목 모델"""
    stock_code: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")
    query_count: int = Field(..., description="조회 횟수")
    
class PopularStocksResponse(BaseResponse):
    """인기 종목 응답 모델"""
    stocks: List[StockPopularityItem]
    period_hours: int = Field(..., description="조회 기간 (시간)")
    total_count: int = Field(..., description="전체 결과 수")

@stats_router.get("/popular-stocks", response_model=PopularStocksResponse)
async def get_popular_stocks(
    hours: int = Query(24, ge=1, le=168, description="조회 기간 (시간, 1~168시간)"),
    limit: int = Query(20, ge=1, le=100, description="반환할 종목 수 (1~100개)"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> PopularStocksResponse:
    """
    최근 N시간 이내에 가장 많이 조회된 종목 상위 M개를 반환합니다.
    
    Args:
        hours: 조회 기간 (기본값: 24시간)
        limit: 반환할 종목 수 (기본값: 20개)
        db: 데이터베이스 세션
        current_session: 현재 사용자 세션
        
    Returns:
        PopularStocksResponse: 인기 종목 목록과 메타데이터
    """
    try:
        logger.info(f"인기 종목 조회 시작: 기간={hours}시간, 제한={limit}개")
        
        # 조회 시작 시간 계산 (현재 시간 - N시간)
        start_time = datetime.now() - timedelta(hours=hours)
        
        # SQL 쿼리 구성
        # stockeasy_chat_sessions 테이블에서 created_at이 지정된 시간 이후이고
        # stock_code와 stock_name이 null이 아닌 레코드들을 대상으로
        # stock_code, stock_name 조합별로 그룹화하여 개수를 세고
        # 개수 순으로 내림차순 정렬하여 상위 N개를 가져옴
        query = select(
            StockChatSession.stock_code,
            StockChatSession.stock_name,
            func.count().label('query_count')
        ).where(
            and_(
                StockChatSession.created_at >= start_time,
                StockChatSession.stock_code.is_not(None),
                StockChatSession.stock_name.is_not(None),
                StockChatSession.stock_code != '',
                StockChatSession.stock_name != ''
            )
        ).group_by(
            StockChatSession.stock_code,
            StockChatSession.stock_name
        ).order_by(
            func.count().desc()
        ).limit(limit)
        
        # 쿼리 실행
        result = await db.execute(query)
        rows = result.fetchall()
        
        # 결과를 모델 객체로 변환
        stocks = []
        for row in rows:
            stock_item = StockPopularityItem(
                stock_code=row.stock_code,
                stock_name=row.stock_name,
                query_count=row.query_count
            )
            stocks.append(stock_item)
        
        logger.info(f"인기 종목 조회 완료: {len(stocks)}개 종목 반환")
        
        # 디버깅을 위한 상위 5개 종목 로그
        if stocks:
            top_stocks = stocks[:5]
            logger.info(f"상위 5개 종목: {[(s.stock_name, s.query_count) for s in top_stocks]}")
        
        return PopularStocksResponse(
            ok=True,
            status_message=f"최근 {hours}시간 인기 종목 조회 완료",
            stocks=stocks,
            period_hours=hours,
            total_count=len(stocks)
        )
        
    except Exception as e:
        error_message = f"인기 종목 조회 중 오류 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        # 특정 오류 타입에 따른 사용자 친화적 메시지 제공
        if "connection" in str(e).lower():
            user_message = "데이터베이스 연결에 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        elif "timeout" in str(e).lower():
            user_message = "요청 처리 시간이 초과되었습니다. 조회 기간을 줄여서 다시 시도해주세요."
        else:
            user_message = "통계 데이터 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=user_message
        )

@stats_router.get("/session-count", response_model=dict)
async def get_session_count(
    hours: int = Query(24, ge=1, le=168, description="조회 기간 (시간, 1~168시간)"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> dict:
    """
    최근 N시간 이내 생성된 채팅 세션 총 개수를 반환합니다.
    
    Args:
        hours: 조회 기간 (기본값: 24시간)
        db: 데이터베이스 세션
        current_session: 현재 사용자 세션
        
    Returns:
        dict: 세션 개수와 메타데이터
    """
    try:
        logger.info(f"세션 개수 조회 시작: 기간={hours}시간")
        
        # 조회 시작 시간 계산
        start_time = datetime.now() - timedelta(hours=hours)
        
        # 총 세션 개수 쿼리
        total_query = select(func.count()).select_from(StockChatSession).where(
            StockChatSession.created_at >= start_time
        )
        
        # 종목이 포함된 세션 개수 쿼리
        with_stock_query = select(func.count()).select_from(StockChatSession).where(
            and_(
                StockChatSession.created_at >= start_time,
                StockChatSession.stock_code.is_not(None),
                StockChatSession.stock_code != ''
            )
        )
        
        # 쿼리 실행
        total_result = await db.execute(total_query)
        total_count = total_result.scalar()
        
        with_stock_result = await db.execute(with_stock_query) 
        with_stock_count = with_stock_result.scalar()
        
        logger.info(f"세션 개수 조회 완료: 총 {total_count}개, 종목 포함 {with_stock_count}개")
        
        return {
            "ok": True,
            "status_message": f"최근 {hours}시간 세션 개수 조회 완료",
            "period_hours": hours,
            "total_sessions": total_count,
            "sessions_with_stock": with_stock_count,
            "sessions_without_stock": total_count - with_stock_count
        }
        
    except Exception as e:
        error_message = f"세션 개수 조회 중 오류 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="세션 개수 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        ) 