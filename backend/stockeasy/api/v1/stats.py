"""
스탁이지 통계 API 라우터.

이 모듈은 스탁이지 DB의 통계 데이터를 제공하는 API 엔드포인트를 제공합니다.
Redis 캐시를 활용하여 성능을 최적화합니다.
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import json
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel, Field
from loguru import logger

from common.core.database import get_db_async
from stockeasy.models.chat import StockChatSession
from common.core.deps import get_current_session
from common.models.user import Session
from common.core.redis import AsyncRedisClient

# 통계 라우터 정의
stats_router = APIRouter(prefix="/stats", tags=["통계"])

# Redis 클라이언트 초기화
redis_client = AsyncRedisClient()

class RankChangeType(str, Enum):
    """순위 변동 타입"""
    UP = "UP"           # 순위 상승
    DOWN = "DOWN"       # 순위 하락
    SAME = "SAME"       # 순위 동일
    NEW = "NEW"         # 신규 진입
    OUT = "OUT"         # 순위 밖으로

class BaseResponse(BaseModel):
    """기본 응답 모델"""
    ok: bool
    status_message: str

class RankChange(BaseModel):
    """순위 변동 정보"""
    change_type: RankChangeType = Field(..., description="순위 변동 타입")
    change_value: int = Field(..., description="순위 변동 수치 (양수: 상승, 음수: 하락)")
    previous_rank: Optional[int] = Field(None, description="이전 순위")

class StockPopularityItem(BaseModel):
    """인기 종목 항목 모델"""
    stock_code: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")
    query_count: int = Field(..., description="조회 횟수")
    rank: int = Field(..., description="현재 순위")
    rank_change: Optional[RankChange] = Field(None, description="순위 변동 정보")
    
class PopularStocksPeriodData(BaseModel):
    """기간별 인기 종목 데이터"""
    stocks: List[StockPopularityItem]
    period_hours: int = Field(..., description="조회 기간 (시간)")
    total_count: int = Field(..., description="전체 결과 수")
    from_cache: bool = Field(False, description="캐시에서 조회 여부")

class PopularStocksResponse(BaseResponse):
    """인기 종목 응답 모델"""
    data_24h: PopularStocksPeriodData = Field(..., description="24시간 데이터")
    data_7d: PopularStocksPeriodData = Field(..., description="7일 데이터")

async def _fetch_popular_stocks_from_db(
    hours: int, 
    limit: int, 
    db: AsyncSession
) -> List[Dict]:
    """
    데이터베이스에서 인기 종목 데이터를 조회합니다.
    
    Args:
        hours: 조회 기간 (시간)
        limit: 반환할 종목 수
        db: 데이터베이스 세션
        
    Returns:
        List[Dict]: 인기 종목 목록 (딕셔너리 형태)
    """
    # 조회 시작 시간 계산 (현재 시간 - N시간)
    start_time = datetime.now() - timedelta(hours=hours)
    
    # SQL 쿼리 구성
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
    
    # 결과를 딕셔너리 리스트로 변환
    stocks = []
    for idx, row in enumerate(rows, 1):
        stock_item = {
            'stock_code': row.stock_code,
            'stock_name': row.stock_name,
            'query_count': row.query_count,
            'rank': idx
        }
        stocks.append(stock_item)
    
    return stocks

def _calculate_rank_changes(
    current_stocks: List[Dict], 
    previous_stocks: List[Dict]
) -> List[StockPopularityItem]:
    """
    순위 변동을 계산합니다.
    
    Args:
        current_stocks: 현재 기간 종목 데이터
        previous_stocks: 이전 기간 종목 데이터
        
    Returns:
        List[StockPopularityItem]: 순위 변동이 포함된 종목 리스트
    """
    # 이전 기간 종목별 순위 매핑
    previous_rank_map = {
        stock['stock_code']: stock['rank'] 
        for stock in previous_stocks
    }
    
    result_stocks = []
    
    for current_stock in current_stocks:
        stock_code = current_stock['stock_code']
        current_rank = current_stock['rank']
        previous_rank = previous_rank_map.get(stock_code)
        
        # 순위 변동 계산
        if previous_rank is None:
            # 신규 진입
            rank_change = RankChange(
                change_type=RankChangeType.NEW,
                change_value=0,
                previous_rank=None
            )
        else:
            # 순위 변동 계산 (이전 순위 - 현재 순위)
            change_value = previous_rank - current_rank
            
            if change_value > 0:
                # 순위 상승 (숫자가 작아짐)
                change_type = RankChangeType.UP
            elif change_value < 0:
                # 순위 하락 (숫자가 커짐)
                change_type = RankChangeType.DOWN
            else:
                # 순위 동일
                change_type = RankChangeType.SAME
            
            rank_change = RankChange(
                change_type=change_type,
                change_value=change_value,
                previous_rank=previous_rank
            )
        
        # StockPopularityItem 생성
        stock_item = StockPopularityItem(
            stock_code=current_stock['stock_code'],
            stock_name=current_stock['stock_name'],
            query_count=current_stock['query_count'],
            rank=current_rank,
            rank_change=rank_change
        )
        result_stocks.append(stock_item)
    
    return result_stocks

@stats_router.get("/popular-stocks", response_model=PopularStocksResponse)
async def get_popular_stocks(
    limit: int = Query(20, ge=1, le=100, description="반환할 종목 수 (1~100개)"),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> PopularStocksResponse:
    """
    인기 종목 통계를 반환합니다.
    24시간 및 7일 데이터를 Redis 캐시를 통해 효율적으로 제공하며,
    순위 변동 정보도 함께 제공합니다.
    
    Args:
        limit: 반환할 종목 수 (기본값: 20개)
        db: 데이터베이스 세션
        current_session: 현재 사용자 세션
        
    Returns:
        PopularStocksResponse: 24시간과 7일 인기 종목 데이터 (순위 변동 포함)
    """
    try:
        logger.info(f"인기 종목 조회 시작: limit={limit}")
        
        # 캐시 키 정의 (limit별로 캐시 분리)
        cache_key_24h = f"stockeasy:popular_stocks:24h:limit_{limit}:v2"
        cache_key_7d = f"stockeasy:popular_stocks:7d:limit_{limit}:v2"
        
        # 24시간 데이터 조회 및 처리
        cached_24h = await redis_client.get_key(cache_key_24h)
        if cached_24h:
            logger.info("24시간 데이터를 캐시에서 조회")
            stocks_24h_with_changes = [StockPopularityItem(**stock) for stock in cached_24h]
            from_cache_24h = True
        else:
            logger.info("24시간 데이터를 DB에서 조회 후 순위 변동 계산")
            # 현재 24시간과 이전 48시간 데이터 조회
            current_24h = await _fetch_popular_stocks_from_db(24, limit, db)
            previous_48h = await _fetch_popular_stocks_from_db(48, limit, db)
            
            # 순위 변동 계산
            stocks_24h_with_changes = _calculate_rank_changes(current_24h, previous_48h)
            
            # 캐시에 저장 (1시간)
            cache_data = [stock.dict() for stock in stocks_24h_with_changes]
            await redis_client.set_key(cache_key_24h, cache_data, expire=3600)
            from_cache_24h = False
        
        # 7일 데이터 조회 및 처리
        cached_7d = await redis_client.get_key(cache_key_7d)
        if cached_7d:
            logger.info("7일 데이터를 캐시에서 조회")
            stocks_7d_with_changes = [StockPopularityItem(**stock) for stock in cached_7d]
            from_cache_7d = True
        else:
            logger.info("7일 데이터를 DB에서 조회 후 순위 변동 계산")
            # 현재 7일과 이전 14일 데이터 조회
            current_7d = await _fetch_popular_stocks_from_db(168, limit, db)  # 7일 = 168시간
            previous_14d = await _fetch_popular_stocks_from_db(336, limit, db)  # 14일 = 336시간
            
            # 순위 변동 계산
            stocks_7d_with_changes = _calculate_rank_changes(current_7d, previous_14d)
            
            # 캐시에 저장 (2시간)
            cache_data = [stock.dict() for stock in stocks_7d_with_changes]
            await redis_client.set_key(cache_key_7d, cache_data, expire=7200)
            from_cache_7d = False
        
        # 응답 데이터 구성
        data_24h = PopularStocksPeriodData(
            stocks=stocks_24h_with_changes,
            period_hours=24,
            total_count=len(stocks_24h_with_changes),
            from_cache=from_cache_24h
        )
        
        data_7d = PopularStocksPeriodData(
            stocks=stocks_7d_with_changes,
            period_hours=168,
            total_count=len(stocks_7d_with_changes),
            from_cache=from_cache_7d
        )
        
        logger.info(f"인기 종목 조회 완료: 24시간 {len(stocks_24h_with_changes)}개, 7일 {len(stocks_7d_with_changes)}개")
        
        # 디버깅을 위한 상위 5개 종목 로그 (순위 변동 포함)
        if stocks_24h_with_changes:
            top_stocks_24h = stocks_24h_with_changes[:5]
            def format_rank_change(stock):
                if not stock.rank_change:
                    return 'N/A'
                change_type = stock.rank_change.change_type.value
                if change_type == 'NEW':
                    return 'NEW'
                elif change_type == 'SAME':
                    return 'SAME(0)'
                elif change_type == 'UP':
                    return f'UP(+{stock.rank_change.change_value})'
                elif change_type == 'DOWN':
                    return f'DOWN({stock.rank_change.change_value})'
                else:
                    return change_type
            
            logger.info(f"24시간 상위 5개 종목: {[(s.stock_name, s.query_count, format_rank_change(s)) for s in top_stocks_24h]}")
        
        if stocks_7d_with_changes:
            top_stocks_7d = stocks_7d_with_changes[:5]
            logger.info(f"7일 상위 5개 종목: {[(s.stock_name, s.query_count, format_rank_change(s)) for s in top_stocks_7d]}")
        
        return PopularStocksResponse(
            ok=True,
            status_message="인기 종목 조회 완료 (순위 변동 포함)",
            data_24h=data_24h,
            data_7d=data_7d
        )
        
    except Exception as e:
        error_message = f"인기 종목 조회 중 오류 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        # 특정 오류 타입에 따른 사용자 친화적 메시지 제공
        if "connection" in str(e).lower():
            user_message = "데이터베이스 연결에 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        elif "timeout" in str(e).lower():
            user_message = "요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
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