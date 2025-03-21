"""Redis 클라이언트 구현"""

from typing import Optional, Any, Dict
import json
from redis import Redis
from common.core.config import settings
from datetime import datetime
from uuid import UUID
import logging
from dateutil import tz

# Create a logger instance
logger = logging.getLogger(__name__)

# 문서 상태 상수
DOCUMENT_STATUS = {
    'REGISTERED': 'REGISTERED',
    'UPLOADING': 'UPLOADING',
    'UPLOADED': 'UPLOADED',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'PARTIAL': 'PARTIAL',
    'ERROR': 'ERROR',
    'DELETED': 'DELETED'
}

class RedisClient:
    # Redis 키 접두사 상수
    TASK_STATUS_PREFIX = "task_status:"
    BATCH_STATUS_PREFIX = "batch_status:"
    DOCUMENT_STATUS_PREFIX = "doc_status:"
    DOCUMENT_PROGRESS_PREFIX = "doc_progress:"
    
    def __init__(self):
        logger.info(f"[RedisClient] Redis URL: {settings.REDIS_URL}")
        self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        
    def _make_key(self, prefix: str, key: str) -> str:
        """Redis 키 생성"""
        return f"{prefix}{key}"
        
    def set_key(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Redis에 키-값 쌍을 저장"""
        try:
            # 기존 키가 있다면 삭제
            self.redis.delete(key)
            
            # 값을 JSON 문자열로 변환
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)
                
            self.redis.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"Redis set_key error: {str(e)}")
            return False
            
    def get_key(self, key: str) -> Optional[Any]:
        """Redis에서 값을 조회"""
        try:
            value = self.redis.get(key)
            if value is None:
                return None
                
            try:
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return value
        except Exception as e:
            logger.error(f"Redis get_key error: {str(e)}")
            return None
            
    def delete_key(self, key: str) -> bool:
        """Redis에서 키를 삭제"""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete_key error: {str(e)}")
            return False
            
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """키의 값을 지정된 양만큼 증가시킵니다.
        
        Args:
            key (str): 증가시킬 키
            amount (int, optional): 증가시킬 양. 기본값은 1.
            
        Returns:
            Optional[int]: 증가 후의 값. 실패시 None.
        """
        try:
            return self.redis.incr(key, amount)
        except Exception as e:
            logger.error(f"Redis incr error: {str(e)}")
            return None
            
    def set_task_status(self, task_id: str, status: str, result: Optional[Any] = None) -> bool:
        """Celery 작업 상태 저장"""
        task_data = {
            "status": status,
            "updated_at": datetime.now(tz.tzutc()).isoformat(),
        }
        if result is not None:
            task_data["result"] = result
            
        key = self._make_key(self.TASK_STATUS_PREFIX, task_id)
        return self.set_key(key, task_data)

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Celery 작업 상태 조회"""
        key = self._make_key(self.TASK_STATUS_PREFIX, task_id)
        return self.get_key(key)

    def set_document_status(self, document_id: str, status: str, error_message: Optional[str] = None) -> bool:
        """문서 상태 설정"""
        status_data = {
            'status': status,
            'updated_at': datetime.now(tz.tzutc()).isoformat()
        }
        if error_message:
            status_data['error_message'] = error_message
            
        key = self._make_key(self.DOCUMENT_STATUS_PREFIX, str(document_id))
        return self.set_key(key, status_data)

    def get_document_status(self, document_id: str) -> Optional[Dict[str, Any]]:
        """문서 상태 조회"""
        key = self._make_key(self.DOCUMENT_STATUS_PREFIX, str(document_id))
        return self.get_key(key)

    def update_document_status(
        self,
        doc_id: UUID,
        doc_status: str,
        metadata: dict = None,
        error: str = None
    ) -> bool:
        """문서 상태 업데이트"""
        try:
            status_data = {
                'status': doc_status,
                'updated_at': datetime.now(tz.tzutc()).isoformat()
            }
            
            if metadata:
                status_data['metadata'] = metadata
            if error:
                status_data['error_message'] = error
                
            key = self._make_key(self.DOCUMENT_STATUS_PREFIX, str(doc_id))
            return self.set_key(key, status_data)
            
        except Exception as e:
            logger.error(f"Redis update_document_status error: {str(e)}")
            return False

    async def update_document_status_async(
        self,
        doc_id: UUID,
        doc_status: str,
        metadata: dict = None,
        error: str = None
    ) -> bool:
        """문서 상태 비동기 업데이트"""
        return self.update_document_status(doc_id, doc_status, metadata, error)


# Redis 클라이언트 인스턴스 생성
redis_client = RedisClient()
