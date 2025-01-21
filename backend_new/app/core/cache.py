import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any
from redis.asyncio import Redis
from redis import Redis as SyncRedis
from app.core.config import settings

class RedisCache:
    """동기 Redis 캐시 매니저"""
    def __init__(self, redis_url: str = "redis://localhost:6379", expire_time: int = 3600):
        """Redis 캐시 매니저 초기화
        
        Args:
            redis_url: Redis 서버 URL
            expire_time: 캐시 만료 시간 (초)
        """
        self.redis = SyncRedis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        self.expire_time = expire_time
    
    def _generate_key(self, document_id: str, query: str) -> str:
        """문서 ID와 쿼리로 캐시 키 생성
        
        Args:
            document_id: 문서 ID
            query: 사용자 쿼리
            
        Returns:
            str: 캐시 키
        """
        combined = f"{document_id}:{query}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, document_id: str, query: str) -> Optional[str]:
        """캐시에서 응답 조회
        
        Args:
            document_id: 문서 ID
            query: 사용자 쿼리
            
        Returns:
            Optional[str]: 캐시된 응답 또는 None
        """
        key = self._generate_key(document_id, query)
        cached = self.redis.get(key)
        if cached:
            print(f"cached : {cached}")
            return json.loads(cached)
        return None
    
    def set(self, document_id: str, query: str, response: str):
        """응답을 캐시에 저장
        
        Args:
            document_id: 문서 ID
            query: 사용자 쿼리
            response: AI 응답
        """
        key = self._generate_key(document_id, query)
        value = json.dumps({
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(seconds=self.expire_time)).isoformat()
        })
        self.redis.set(key, value, ex=self.expire_time)
    
    def close(self):
        """Redis 연결 종료"""
        self.redis.close()

class AsyncRedisCache:
    """비동기 Redis 캐시 매니저"""
    def __init__(self, redis_url: str = "redis://localhost:6379", expire_time: int = 3600):
        """Redis 캐시 매니저 초기화
        
        Args:
            redis_url: Redis 서버 URL
            expire_time: 캐시 만료 시간 (초)
        """
        self.redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        self.expire_time = expire_time
    
    def _generate_key(self, document_id: str, query: str) -> str:
        """문서 ID와 쿼리로 캐시 키 생성
        
        Args:
            document_id: 문서 ID
            query: 사용자 쿼리
            
        Returns:
            str: 캐시 키
        """
        # 문서 ID와 쿼리를 합쳐서 해시 생성
        # 문서 ID와 쿼리를 합쳐서 해시 생성
        combined = f"{document_id}:{query}"
    #async def get(self, document_id: str, query: str) -> Optional[str]:
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def get(self, document_id: str, query: str) -> Optional[str]:
        """캐시에서 응답 조회
        
        Args:
            document_id: 문서 ID
            query: 사용자 쿼리
            
        Returns:
            Optional[str]: 캐시된 응답 또는 None
        """
        key = self._generate_key(document_id, query)
        cached = await self.redis.get(key)
        if cached:
            print(f"cached : {cached}")
            return json.loads(cached)
        return None
    
    async def set(self, document_id: str, query: str, response: str):
        """응답을 캐시에 저장
        
        Args:
            document_id: 문서 ID
            query: 사용자 쿼리
            response: AI 응답
        """
        key = self._generate_key(document_id, query)
        value = json.dumps({
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(seconds=self.expire_time)).isoformat()
        })
        await self.redis.set(key, value, ex=self.expire_time)
    
    async def close(self):
        """Redis 연결 종료"""
        await self.redis.close()
