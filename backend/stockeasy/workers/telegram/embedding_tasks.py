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
from sqlalchemy import func
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
        now = datetime.now(tz=timezone.utc)
        current_hour = now.hour

        # 현재 시간과 마지막 실행 시간의 차이를 계산
        if self._last_execution_time.tzinfo is None:
            # _last_execution_time에 시간대 정보가 없는 경우 UTC로 설정
            last_execution_with_tz = self._last_execution_time.replace(tzinfo=timezone.utc)
        else:
            last_execution_with_tz = self._last_execution_time
            
        time_diff = now - last_execution_with_tz

        # 400개 3분. 800개 6분.
        if current_hour > 19 or current_hour < 7:
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
def process_new_messages(self, batch_size: int = 800) -> int:
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
            .filter(TelegramMessage.message_text.is_not(None))  # 메시지 텍스트가 None이 아닌 것
            .filter(func.length(func.trim(TelegramMessage.message_text)) >= 10)  # 텍스트 길이가 10 이상인 것만
            .limit(batch_size)
            .all()
        )
        
        if not messages:
            logger.info("임베딩할 새로운 메시지가 없습니다.")
            return 0
        
        logger.info(f"{len(messages)}개의 새로운 메시지를 임베딩합니다.")
        
        # 메시지의 ID 목록 기록
        message_ids = [message.message_id for message in messages]
        logger.debug(f"임베딩 처리할 메시지 ID: {message_ids}")
        
        # 배치 임베딩 처리 - 결과는 전체 성공 여부만 반환
        success = self.embedding_service.embed_telegram_messages_batch(messages)
        
        if success:
            # 개별 메시지의 임베딩 상태 확인
            success_count = 0
            for message in messages:
                # 벡터 저장소에서 각 메시지의 벡터 ID를 확인하여 실제 저장 여부 확인
                vector_id = f"{message.channel_id}_{message.message_id}"
                exists = self.embedding_service.vector_store.vector_exists(vector_id)
                
                if exists:
                    # 실제로 벡터가 저장된 메시지만 임베딩 성공으로 표시
                    message.is_embedded = True
                    success_count += 1
                else:
                    logger.warning(f"메시지 벡터 저장 실패 (vector_id: {vector_id}), len({message.message_text})")
            
            # 변경사항 저장
            self.db.commit()
            logger.info(f"{success_count}개 메시지 임베딩 완료 (전체 {len(messages)}개 중)")
            return success_count
        else:
            logger.error("메시지 임베딩 실패")
            return 0
        
    except Exception as e:
        logger.error(f"임베딩 태스크 실행 중 오류 발생: {str(e)}")
        raise self.retry(exc=e)
