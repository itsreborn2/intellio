"""
텔레그램 메시지 임베딩 태스크

수집된 텔레그램 메시지를 임베딩하고 벡터 저장소에 저장하는 비동기 태스크들을 정의합니다.
"""

from celery import Task

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional

from common.core.database import SessionLocal

from stockeasy.core.celery_app import celery
from stockeasy.models.telegram_message import TelegramMessage
from stockeasy.services.telegram.embedding import TelegramEmbeddingService
from loguru import logger
#logger = logging.getLogger(__name__)

class EmbeddingTask(Task):
    """텔레그램 메시지 임베딩 태스크
    
    수집된 메시지를 벡터화하고 저장하는 커스텀 Celery 태스크입니다.
    """
    _db = None
    _embedding_service = None
    _last_execution_time = datetime.min

    @property
    def db(self) -> Session:
        """데이터베이스 세션
        
        Returns:
            Session: SQLAlchemy 데이터베이스 세션
        """
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
        """태스크 종료 후 정리 작업"""
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
            should_run = time_diff.total_seconds() >= 30 * 60  # 60분
        else:
            # 7시 ~ 17시: 5분마다 실행
            should_run = time_diff.total_seconds() >= 6 * 60  # 20분

        if should_run:
            self._last_execution_time = now
            return True
        return False

@celery.task(
    bind=True,
    base=EmbeddingTask,
    name="stockeasy.workers.telegram.embedding_tasks.process_new_messages",
    queue="embedding-processing",
    max_retries=3,
    soft_time_limit=60,  # 1분 제한
)
def process_new_messages(self, batch_size: int = 400) -> int:
    """새로 수집된 메시지를 임베딩 처리하는 태스크
    
    아직 임베딩되지 않은 메시지들을 가져와서 벡터화하고 저장합니다.
    
    Args:
        batch_size (int, optional): 한 번에 처리할 메시지 수. Defaults to 50.
        
    Returns:
        int: 처리된 메시지 수
    """
    try:
        bStart = False
        if self.should_execute():
            bStart = True

        if not bStart:
            return 0

        
        logger.warning('-'*100)
        logger.warning(f"임베딩 태스크 시작 (batch_size: {batch_size})")
        # 임베딩되지 않은 메시지 조회
        messages: List[TelegramMessage] = (
            self.db.query(TelegramMessage)
            .filter(TelegramMessage.is_embedded.is_(False))
            .limit(batch_size)
            .all()
        )
        
        if not messages:
            logger.info("임베딩할 새로운 메시지가 없습니다.")
            return 0
        
        logger.info(f"{len(messages)}개의 새로운 메시지를 임베딩합니다.")
        
        # 배치 임베딩 처리
        success = self.embedding_service.embed_telegram_messages_batch(messages)
        
        if success:
            # 임베딩 상태 업데이트
            for message in messages:
                message.is_embedded = True
            
            # 변경사항 저장
            self.db.commit()
            logger.info(f"{len(messages)}개 메시지 임베딩 완료")
            return len(messages)
        else:
            logger.error("메시지 임베딩 실패")
            return 0
        
    except Exception as e:
        logger.error(f"임베딩 태스크 실행 중 오류 발생: {str(e)}")
        raise self.retry(exc=e)
