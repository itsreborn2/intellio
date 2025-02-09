import asyncio
from celery import Task
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.celery_app import celery
from app.services.telegram.collector import CollectorService
from app.services.telegram.embedding import TelegramEmbeddingService
from app.core.database import SessionLocal
from app.models.telegram_message import TelegramMessage

logger = logging.getLogger(__name__)

class CollectorTask(Task):
    """텔레그램 메시지 수집 태스크
    
    비동기 작업을 처리하기 위한 커스텀 Celery 태스크입니다.
    """
    _db = None
    _embedding_service = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def embedding_service(self) -> TelegramEmbeddingService:
        """임베딩 서비스
        
        Returns:
            TelegramEmbeddingService: 텔레그램 메시지 임베딩 서비스
        """
        if self._embedding_service is None:
            self._embedding_service = TelegramEmbeddingService()
        return self._embedding_service

    def after_return(self, *args, **kwargs):
        """태스크 완료 후 DB 세션을 정리합니다."""
        if self._db is not None:
            self._db.close()
            self._db = None

@celery.task(
    base=CollectorTask,
    bind=True,
    name="app.workers.telegram.collector_tasks.embed_messages",
    queue="telegram-processing",
)
def embed_messages(self, message_ids: list[int]) -> bool:
    """수집된 텔레그램 메시지를 임베딩하는 태스크
    
    Args:
        message_ids (list[int]): 임베딩할 메시지 ID 리스트
        
    Returns:
        bool: 임베딩 성공 여부
    """
    try:
        # DB에서 메시지 조회
        messages = self.db.query(TelegramMessage).filter(
            TelegramMessage.message_id.in_(message_ids)
        ).all()
        
        if not messages:
            logger.warning(f"임베딩할 메시지가 없습니다: {message_ids}")
            return False
            
        # 비동기 임베딩 처리를 동기적으로 실행
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(
            self.embedding_service.embed_telegram_messages_batch(messages)
        )
        
        if success:
            # 임베딩 상태 업데이트
            for message in messages:
                message.is_embedded = True
            
            # 변경사항 저장
            self.db.commit()
            logger.info(f"메시지 {len(messages)}개 임베딩 완료")
        else:
            logger.error(f"메시지 임베딩 실패: {message_ids}")
            
        return success
        
    except Exception as e:
        logger.error(f"임베딩 처리 중 오류 발생: {str(e)}")
        return False

@celery.task(
    base=CollectorTask,
    bind=True,
    name="app.workers.telegram.collector_tasks.collect_messages",
    queue="telegram-processing",
    rate_limit="60/m",  # 분당 최대 60개 작업
    max_retries=3,
    soft_time_limit=60,  # 1분 제한
)
def collect_messages(self):
    """모든 설정된 채널에서 메시지를 수집하는 태스크
    
    Returns:
        int: 수집된 총 메시지 수
    """
    try:
        collector = CollectorService(self.db)
        
        # 비동기 수집 실행
        loop = asyncio.get_event_loop()
        messages = loop.run_until_complete(collector.collect_all_channels())
        
        if messages:
            # 수집된 메시지 ID 리스트
            message_ids = [msg['message_id'] for msg in messages]
            
            # 임베딩 태스크 체이닝 (동기적으로 실행)
            embed_messages.delay(message_ids)
            
            logger.info(f"총 {len(messages)}개의 메시지 수집 완료 및 임베딩 태스크 시작")
            return len(messages)
        else:
            logger.info("수집된 새 메시지가 없습니다")
            return 0
            
    except Exception as e:
        logger.error(f"메시지 수집 중 오류 발생: {str(e)}")
        raise

@celery.task(
    base=CollectorTask,
    bind=True,
    name="app.workers.telegram.collector_tasks.cleanup_daily_messages",
    queue="telegram-processing"
)
def cleanup_daily_messages(self) -> int:
    """텔레그램 메시지 정리 태스크
    
    1. PostgreSQL DB: 당일 수집된 메시지를 삭제합니다. (매일 23:59 실행)
    2. 벡터 저장소: 90일이 지난 메시지를 삭제합니다.
    
    이미 임베딩된 메시지는 벡터 저장소에 저장되어 있으므로, 
    PostgreSQL에서는 더 이상 보관할 필요가 없습니다.
    벡터 저장소의 메시지는 90일간 보관 후 삭제됩니다.
    
    Returns:
        int: 삭제된 메시지 수
    """
    try:
        # 오늘 자정 이전의 메시지만 삭제 (PostgreSQL)
        today_midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # 90일 이전 날짜 계산 (벡터 저장소)
        ninety_days_ago = today_midnight - timezone.timedelta(days=90)
        
        # 삭제할 메시지 조회
        messages = self.db.query(TelegramMessage).filter(
            TelegramMessage.collected_at < today_midnight
        ).all()
        
        if messages:
            # 채널별로 메시지 그룹화
            channel_messages = {}
            for msg in messages:
                if msg.channel_id not in channel_messages:
                    channel_messages[msg.channel_id] = []
                channel_messages[msg.channel_id].append(msg)
            
            # 채널별로 벡터 저장소에서 90일 이전 메시지 삭제
            loop = asyncio.get_event_loop()
            for channel_id, channel_msgs in channel_messages.items():
                # 90일 이전 메시지만 필터링
                old_messages = [
                    msg for msg in channel_msgs 
                    if msg.created_at < ninety_days_ago
                ]
                
                if old_messages:
                    loop.run_until_complete(
                        self.embedding_service.delete_channel_messages(
                            channel_id,
                            before_date=ninety_days_ago
                        )
                    )
                    logger.info(f"채널 {channel_id}의 90일 이전 메시지 {len(old_messages)}개 삭제 완료")
            
            # PostgreSQL DB에서 메시지 삭제
            deleted = self.db.query(TelegramMessage).filter(
                TelegramMessage.collected_at < today_midnight
            ).delete()
            
            self.db.commit()
            logger.info(f"총 {deleted}개의 메시지 DB에서 삭제 완료")
            return deleted
        
        return 0
        
    except Exception as e:
        logger.error(f"메시지 삭제 중 오류 발생: {str(e)}")
        self.db.rollback()
        raise
