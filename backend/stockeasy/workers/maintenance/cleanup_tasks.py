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
    15일 이상 경과한 공유 채팅 세션을 삭제합니다.
    세션과 연결된 메시지는 cascade 옵션에 의해 자동으로 삭제됩니다.
    """
    logger.info("오래된 공유 채팅 세션 정리 작업 시작")
    
    try:
        # 비동기 함수를 Celery 태스크 내에서 실행
        session_cleanup_result = _cleanup_old_sessions()
        deleted_count = session_cleanup_result
        
        logger.info(f"공유 채팅 세션 정리 완료: {deleted_count}개 세션 삭제됨")
        return {"status": "success", "deleted_count": deleted_count}
    
    except Exception as e:
        logger.error(f"공유 채팅 세션 정리 중 오류 발생: {str(e)}")
        return {"status": "error", "error": str(e)}

async def _cleanup_old_sessions():
    """
    15일 이상 경과한 공유 채팅 세션을 비동기적으로 삭제합니다.
    """
    # 15일 전 날짜 계산
    cutoff_date = datetime.now() - timedelta(days=15)
    deleted_count = 0
    
    async for session in get_db_session():
        try:
            # 15일 이상 경과한 세션 조회
            old_sessions_query = select(ShareStockChatSession).where(
                ShareStockChatSession.created_at < cutoff_date
            )
            result = await session.execute(old_sessions_query)
            old_sessions = result.scalars().all()
            
            # 로그에 삭제할 세션 정보 기록
            if old_sessions:
                logger.info(f"삭제 예정 세션 수: {len(old_sessions)}")
                for old_session in old_sessions:
                    logger.info(f"삭제 예정 세션: ID={old_session.id}, 생성일={old_session.created_at}")
                    # 세션 삭제 (연결된 메시지는 cascade로 자동 삭제됨)
                    await session.delete(old_session)
                
                # 변경사항 커밋
                await session.commit()
                deleted_count = len(old_sessions)
            else:
                logger.info("삭제할 오래된 공유 세션이 없습니다")
                
        except Exception as e:
            await session.rollback()
            logger.error(f"세션 삭제 중 오류 발생: {str(e)}")
            raise e
            
    return deleted_count 