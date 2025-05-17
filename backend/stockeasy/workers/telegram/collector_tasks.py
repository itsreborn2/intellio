import asyncio
from celery import Task
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from common.core.database import get_db, SessionLocal

from stockeasy.core.celery_app import celery
from stockeasy.services.telegram.collector import CollectorService
from stockeasy.services.telegram.embedding import TelegramEmbeddingService
from stockeasy.models.telegram_message import TelegramMessage

from loguru import logger

class CollectorTask(Task):
    """텔레그램 메시지 수집 태스크
    
    비동기 작업을 처리하기 위한 커스텀 Celery 태스크입니다.
    """
    _db = None
    _embedding_service = None
    _last_execution_time = datetime.min

    @property
    def db(self) -> Session:
        """데이터베이스 세션을 반환합니다."""
        if self._db is None:
            # 세션 생성
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from common.core.config import settings
            
            #engine = create_engine(settings.DATABASE_URL)
            #SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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

    def should_execute(self) -> bool:
        now = datetime.now()
        current_hour = now.hour
        
        # 현재 시간과 마지막 실행 시간의 차이를 계산
        time_diff = now - self._last_execution_time
        
        if current_hour >= 17 or current_hour < 7:
            # 17시 ~ 7시: 20분마다 실행
            should_run = time_diff.total_seconds() >= 20 * 60  # 20분
        else:
            # 7시 ~ 17시: 5분마다 실행
            should_run = time_diff.total_seconds() >= 5 * 60  # 5분
        
        if should_run:
            self._last_execution_time = now
            return True
        return False

@celery.task(
    base=CollectorTask,
    bind=True,
    name="stockeasy.workers.telegram.collector_tasks.collect_messages",
    queue="telegram-processing",
    rate_limit="60/m",  # 분당 최대 60개 작업
    #max_retries=3,
    soft_time_limit=60,  # 1분 제한
)
def collect_messages(self):
    """모든 설정된 채널에서 메시지를 수집하는 태스크
    
    Returns:
        int: 수집된 총 메시지 수
    """
    try:
        bStart = False
        if self.should_execute():
            bStart = True

        if not bStart:
            return 0

        logger.warning('='*100)
        logger.warning(f"[Telegram Collector] collect_messages 실행")

        collector = CollectorService(self.db)
                 
        
        # 새로운 이벤트 루프 생성 및 설정
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            messages = loop.run_until_complete(collector.collect_all_channels())
            
            if messages:
                logger.info(f"총 {len(messages)}개의 메시지 수집 완료")
                return len(messages)
            return 0
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.exception(f"메시지 수집 중 오류 발생: {str(e)}", exc_info=True)
        raise

@celery.task(
    base=CollectorTask,
    bind=True,
    name="stockeasy.workers.telegram.collector_tasks.cleanup_daily_messages",
    queue="telegram-processing"
)
def cleanup_daily_messages(self) -> int:
    """텔레그램 메시지 정리 태스크
    
    1. PostgreSQL DB: 당일 수집된 메시지를 삭제합니다. (매일 23:59 실행)
    2. 벡터 저장소: 365일이 지난 메시지를 삭제합니다.
    
    이미 임베딩된 메시지는 벡터 저장소에 저장되어 있으므로, 
    PostgreSQL에서는 더 이상 보관할 필요가 없습니다.
    벡터 저장소의 메시지는 365일간 보관 후 삭제됩니다.
    
    Returns:
        int: 삭제된 메시지 수
    """
    try:
        logger.info(f"cleanup_daily_messages 실행")
        # 오늘 자정 이전의 메시지만 삭제 (PostgreSQL)
        today_midnight = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # 20일 이전 날짜 계산 (벡터 저장소)
        ninety_days_ago = today_midnight - timedelta(days=20)
        
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
                    if msg.message_created_at < ninety_days_ago
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
