import json

from loguru import logger # loguru import 추가
from typing import Dict, Any, List, Optional, Tuple, Union, TypeVar, Generic, Callable
import asyncio
from functools import wraps

from common.core.redis import AsyncRedisClient

# logger = logging.getLogger(__name__) # 삭제

T = TypeVar('T')


class FinancialCacheUtil:
    """
    재무 데이터 캐싱 유틸리티
    """
    
    def __init__(self):
        self.redis = AsyncRedisClient()
        self.prefix = "stockeasy:"
        self.expire_time = 60 * 60 * 24  # 24시간
    
    async def get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        캐시에서 데이터 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            캐시된 데이터 또는 None
        """
        full_key = f"{self.prefix}{key}"
        try:
            data = await self.redis.get(full_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"캐시 조회 중 오류 발생: {e}")
            return None
    
    async def set_cache(self, key: str, data: Dict[str, Any], expire: Optional[int] = None) -> bool:
        """
        데이터를 캐시에 저장
        
        Args:
            key: 캐시 키
            data: 저장할 데이터
            expire: 만료 시간(초), None인 경우 기본값 사용
            
        Returns:
            저장 성공 여부
        """
        full_key = f"{self.prefix}{key}"
        try:
            data_str = json.dumps(data)
            await self.redis.set(full_key, data_str, expire or self.expire_time)
            return True
        except Exception as e:
            logger.error(f"캐시 저장 중 오류 발생: {e}")
            return False
    
    async def delete_cache(self, key: str) -> bool:
        """
        캐시에서 데이터 삭제
        
        Args:
            key: 캐시 키
            
        Returns:
            삭제 성공 여부
        """
        full_key = f"{self.prefix}{key}"
        try:
            await self.redis.delete(full_key)
            return True
        except Exception as e:
            logger.error(f"캐시 삭제 중 오류 발생: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> bool:
        """
        패턴에 맞는 캐시 키 삭제
        
        Args:
            pattern: 삭제할 키 패턴
            
        Returns:
            삭제 성공 여부
        """
        full_pattern = f"{self.prefix}{pattern}"
        try:
            keys = await self.redis.keys(f"{full_pattern}*")
            if keys:
                await self.redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"패턴 캐시 삭제 중 오류 발생: {e}, 패턴: {pattern}")
            return False
    
    # 특정 회사의 재무 데이터 캐시 키
    def get_company_financial_cache_key(self, company_code: str) -> str:
        """회사 코드 기반 캐시 키"""
        return f"summary:{company_code}"
    
    # 특정 항목의 재무 데이터 캐시 키
    def get_item_financial_cache_key(self, item_code: str) -> str:
        """항목 코드 기반 캐시 키"""
        return f"item:{item_code}"
    
    # 캐시 키 생성 (회사+항목+기간)
    def get_financial_cache_key(
        self, company_code: Optional[str] = None, 
        item_codes: Optional[List[str]] = None,
        start_year_month: Optional[int] = None,
        end_year_month: Optional[int] = None
    ) -> str:
        """재무 데이터 캐시 키 생성"""
        key_parts = ["financial"]
        
        if company_code:
            key_parts.append(f"company:{company_code}")
            
        if item_codes:
            key_parts.append(f"items:{','.join(sorted(item_codes))}")
            
        if start_year_month:
            key_parts.append(f"start:{start_year_month}")
            
        if end_year_month:
            key_parts.append(f"end:{end_year_month}")
            
        return ":".join(key_parts)


# 캐시 데코레이터
def cached(key_fn: Callable, expire: Optional[int] = None):
    """
    함수 결과를 캐싱하는 데코레이터
    
    Args:
        key_fn: 캐시 키를 생성하는 함수
        expire: 캐시 만료 시간 (초)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = key_fn(*args, **kwargs)
            cache_util = FinancialCacheUtil()
            
            # 캐시에서 조회
            cached_data = await cache_util.get_cache(cache_key)
            if cached_data is not None:
                logger.debug(f"캐시에서 데이터 로드: {cache_key}")
                return cached_data
            
            # 캐시 없음, 함수 실행
            result = await func(*args, **kwargs)
            
            # 결과 캐싱
            if result is not None:
                await cache_util.set_cache(cache_key, result, expire)
                
            return result
        return wrapper
    return decorator 