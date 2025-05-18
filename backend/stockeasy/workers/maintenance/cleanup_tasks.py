import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from stockeasy.core.celery_app import celery
from stockeasy.models.chat import ShareStockChatSession
from common.core.database import get_db_session

logger = logging.getLogger(__name__)

@celery.task(name="stockeasy.workers.maintenance.cleanup_tasks.cleanup_old_shared_sessions")
def cleanup_old_shared_sessions():
    """
    15일 이상 경과한 공유 채팅 세션을 확인합니다.
    이전에는 이 함수가 만료된 세션을 삭제했으나, 이제는 만료된 세션을 로깅만 합니다.
    실제 만료 여부는 API 호출 시 동적으로 확인합니다.
    """
    logger.info("오래된 공유 채팅 세션 확인 작업 시작")
    
    try:
        # 비동기 함수를 Celery 태스크 내에서 실행
        expired_count = _check_expired_sessions()
        
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