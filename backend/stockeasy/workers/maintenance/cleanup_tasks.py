import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from stockeasy.core.celery_app import celery
from stockeasy.models.chat import ShareStockChatSession
from common.core.database import get_db_session
from stockeasy.services.web_search_cache_service import WebSearchCacheService

logger = logging.getLogger(__name__)

@celery.task(name="stockeasy.workers.maintenance.cleanup_tasks.cleanup_old_data")
def cleanup_old_data():
    """
    오래된 데이터를 삭제합니다.
    """
    logger.info("오래된 데이터 삭제 작업 시작")

    # 공유채팅 세션 정리
    cleanup_old_shared_sessions()

    # 웹검색 캐싱 데이터 정리
    cleanup_web_search_cache_task()
    
###################
# 공유 채팅 세션 정리
###################
def cleanup_old_shared_sessions():
    """
    15일 이상 경과한 공유 채팅 세션을 확인합니다.
    이전에는 이 함수가 만료된 세션을 삭제했으나, 이제는 만료된 세션을 로깅만 합니다.
    실제 만료 여부는 API 호출 시 동적으로 확인합니다.
    """
    logger.info("오래된 공유 채팅 세션 확인 작업 시작")
    
    try:
        # 비동기 함수를 Celery 태스크 내에서 실행
        expired_count = asyncio.run(_check_expired_sessions())
        
        logger.info(f"공유 채팅 세션 확인 완료: {expired_count}개 만료된 세션 발견")
        return {"status": "success", "expired_count": expired_count}
    
    except Exception as e:
        logger.error(f"공유 채팅 세션 확인 중 오류 발생: {str(e)}")
        return {"status": "error", "error": str(e)}

async def _check_expired_sessions():
    """
    15일 이상 경과한 공유 채팅 세션을 확인하고 로깅합니다.
    세션은 삭제하지 않고, 만료 상태만 확인합니다.
    """
    # 15일 전 날짜 계산
    cutoff_date = datetime.now() - timedelta(days=15)
    expired_count = 0
    
    async for session in get_db_session():
        try:
            # 15일 이상 경과한 세션 조회
            expired_sessions_query = select(ShareStockChatSession).where(
                ShareStockChatSession.created_at < cutoff_date
            )
            result = await session.execute(expired_sessions_query)
            expired_sessions = result.scalars().all()
            
            # 로그에 만료된 세션 정보 기록
            if expired_sessions:
                expired_count = len(expired_sessions)
                logger.info(f"만료된 세션 수: {expired_count}")
                for expired_session in expired_sessions:
                    logger.info(f"만료된 세션: ID={expired_session.id}, 생성일={expired_session.created_at}, 조회수={expired_session.view_count}")
            else:
                logger.info("만료된 공유 세션이 없습니다")
                
        except Exception as e:
            logger.error(f"세션 확인 중 오류 발생: {str(e)}")
            raise e
            
    return expired_count 

###################
# 웹 검색 캐시 정리
###################
def cleanup_web_search_cache_task(max_age_days: int = 15, exclude_min_hits: int = 5) -> None:
    """
    웹 검색 캐시를 정리하는 Celery 작업입니다.
    
    Args:
        max_age_days: 최대 보관 일수 (기본값: 15일)
        exclude_min_hits: 이 값 이상의 히트 카운트를 가진 항목은 보존
    """
    # asyncio를 통해 비동기 함수 실행
    asyncio.run(_cleanup_web_search_cache_async(max_age_days, exclude_min_hits))
    
async def _cleanup_web_search_cache_async(max_age_days: int = 15, exclude_min_hits: int = 5) -> None:
    """
    웹 검색 캐시를 정리하는 비동기 함수입니다.
    
    Args:
        max_age_days: 최대 보관 일수 (기본값: 15일)
        exclude_min_hits: 이 값 이상의 히트 카운트를 가진 항목은 보존
    """
    logger.info(f"웹 검색 캐시 정리 작업 시작: {max_age_days}일 이상 및 {exclude_min_hits} 미만 히트 항목 삭제")
    
    try:
        # DB 세션 생성
        async for db in get_db_session():
            try:
                # 캐시 서비스 초기화
                cache_service = WebSearchCacheService(db)
                
                # 캐시 정리 실행
                deleted_count = await cache_service.cleanup_old_cache(
                    max_age_days=max_age_days,
                    exclude_min_hits=exclude_min_hits
                )
                
                logger.info(f"웹 검색 캐시 정리 완료: {deleted_count}개 항목 삭제됨")
                
                # 캐시 통계 수집 (나중에 필요하면 구현)
                # await collect_cache_statistics(db)
                
                break  # 작업이 성공적으로 완료되면 루프 종료
                
            except Exception as e:
                logger.error(f"캐시 정리 중 오류 발생: {str(e)}", exc_info=True)
                raise
    except Exception as e:
        logger.error(f"DB 세션 생성 중 오류 발생: {str(e)}", exc_info=True)