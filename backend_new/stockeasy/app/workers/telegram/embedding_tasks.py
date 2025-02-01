"""
텔레그램 메시지 임베딩 태스크

수집된 텔레그램 메시지를 Vertex AI를 사용하여 벡터화하고 Pinecone에 저장하는 비동기 태스크들을 정의합니다.
"""

from celery import Task
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional

from app.core.celery_app import celery
from app.core.database import SessionLocal
from app.models.telegram_message import TelegramMessage
from app.services.telegram.embedding import EmbeddingService
from app.services.embedding_models import EmbeddingModelType

logger = logging.getLogger(__name__)

class EmbeddingTask(Task):
    """텔레그램 메시지 임베딩 태스크
    
    수집된 메시지를 벡터화하고 Pinecone에 저장하는 커스텀 Celery 태스크입니다.
    """
    _db = None
    _embedding_service = None

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
    def embedding_service(self) -> EmbeddingService:
        """임베딩 서비스
        
        Returns:
            EmbeddingService: 텔레그램 메시지 임베딩 서비스
        """
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService(index_name="telegram")
        return self._embedding_service

    def after_return(self, *args, **kwargs):
        """태스크 종료 후 정리 작업"""
        if self._db is not None:
            self._db.close()
            self._db = None

@celery.task(
    bind=True,
    base=EmbeddingTask,
    name="app.workers.telegram.embedding_tasks.process_new_messages",
    max_retries=3
)
def process_new_messages(self, batch_size: int = 50) -> int:
    """새로 수집된 메시지를 임베딩 처리하는 태스크
    
    아직 임베딩되지 않은 메시지들을 가져와서 벡터화하고 Pinecone에 저장합니다.
    
    Args:
        batch_size (int, optional): 한 번에 처리할 메시지 수. Defaults to 50.
        
    Returns:
        int: 처리된 메시지 수
    """
    try:
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
        
        # 메시지 임베딩 및 Pinecone 저장
        for message in messages:
            try:
                # 메시지 텍스트 준비
                text = message.text or ""
                if message.has_document:
                    text += f"\n[첨부파일: {message.document_name}]"
                
                # 메타데이터 준비
                metadata = {
                    "message_id": str(message.id),
                    "channel_id": message.channel_id,
                    "channel_title": message.channel_title,
                    "created_at": message.created_at.isoformat(),
                    "has_document": message.has_document,
                    "document_gcs_path": message.document_gcs_path if message.has_document else None
                }
                
                # 임베딩 및 저장
                self.embedding_service.embed_and_store(
                    text=text,
                    metadata=metadata,
                    model_type=EmbeddingModelType.VERTEX_AI
                )
                
                # 임베딩 상태 업데이트
                message.is_embedded = True
                message.embedded_at = datetime.now(timezone.utc)
                
            except Exception as e:
                logger.error(f"메시지 {message.id} 임베딩 중 오류 발생: {str(e)}")
                continue
        
        # 변경사항 저장
        self.db.commit()
        
        return len(messages)
        
    except Exception as e:
        logger.error(f"임베딩 태스크 실행 중 오류 발생: {str(e)}")
        raise self.retry(exc=e)
