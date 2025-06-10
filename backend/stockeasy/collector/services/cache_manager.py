"""
Redis 캐시 매니저
종목코드 <-> 종목명 매핑 및 실시간 데이터 캐싱
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

import redis.asyncio as redis
from redis.asyncio import Redis
from pydantic import BaseModel
from loguru import logger

from stockeasy.collector.core.config import get_settings
from stockeasy.collector.core.logger import LoggerMixin, LogContext
from stockeasy.collector.schemas.stock_schemas import StockRealtimeResponse


class CacheManager(LoggerMixin):
    """Redis 캐시 매니저"""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client: Optional[Redis] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """캐시 매니저 초기화"""
        if self._initialized:
            return
        
        with LogContext(self.logger, "캐시 매니저 초기화") as ctx:
            try:
                # Redis 클라이언트 생성
                self.redis_client = redis.from_url(
                    self.settings.REDIS_URL,
                    password=self.settings.REDIS_PASSWORD,
                    decode_responses=True,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    health_check_interval=30
                )
                
                # 연결 테스트
                await self.redis_client.ping()
                ctx.log_progress("Redis 연결 성공")
                
                # 기본 네임스페이스 설정
                self._init_namespaces()
                
                self._initialized = True
                ctx.log_progress("캐시 매니저 초기화 완료")
                
            except Exception as e:
                ctx.logger.error(f"캐시 매니저 초기화 실패: {e}")
                raise
    
    def _init_namespaces(self) -> None:
        """캐시 네임스페이스 정의"""
        self.namespaces = {
            'symbol_to_name': 'stock:symbol_to_name',
            'name_to_symbol': 'stock:name_to_symbol',
            'realtime': 'stock:realtime',
            'price': 'stock:price',
            'supply_demand': 'stock:supply_demand',
            'etf_components': 'etf:components',
            'market_status': 'market:status',
            'trading_calendar': 'market:calendar',
            'stats': 'collector:stats'
        }
    
    async def close(self) -> None:
        """Redis 연결 종료"""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Redis 연결 종료")
    
    async def is_healthy(self) -> bool:
        """캐시 매니저 상태 확인"""
        try:
            if not self.redis_client:
                return False
            await self.redis_client.ping()
            return True
        except Exception:
            return False
    
    # ===========================================
    # 일반 캐시 관리
    # ===========================================
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """
        일반 캐시 데이터 조회
        
        Args:
            key (str): 캐시 키
            
        Returns:
            Optional[Any]: 캐시된 데이터 또는 None
        """
        try:
            data = await self.redis_client.get(key)
            if data:
                return self._deserialize_data(json.loads(data))
            return None
            
        except Exception as e:
            self.logger.error(f"캐시 조회 실패 [{key}]: {e}")
            return None
    
    async def set_cache(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """
        일반 캐시 데이터 저장
        
        Args:
            key (str): 캐시 키
            data (Any): 저장할 데이터
            ttl (Optional[int]): TTL (초), None인 경우 기본값 사용
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            serialized_data = self._serialize_data(data)
            
            if ttl:
                await self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(serialized_data, ensure_ascii=False)
                )
            else:
                await self.redis_client.set(
                    key,
                    json.dumps(serialized_data, ensure_ascii=False)
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"캐시 저장 실패 [{key}]: {e}")
            return False
    
    async def delete_cache_key(self, key: str) -> bool:
        """
        특정 캐시 키 삭제
        
        Args:
            key (str): 삭제할 캐시 키
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            deleted_count = await self.redis_client.delete(key)
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"캐시 키 삭제 실패 [{key}]: {e}")
            return False
    
    # ===========================================
    # 종목 정보 캐싱
    # ===========================================
    
    async def set_symbol_mapping(self, symbol: str, name: str) -> None:
        """종목코드 <-> 종목명 매핑 저장"""
        try:
            pipeline = self.redis_client.pipeline()
            
            # 종목코드 -> 종목명
            pipeline.hset(self.namespaces['symbol_to_name'], symbol, name)
            
            # 종목명 -> 종목코드 (검색용)
            pipeline.hset(self.namespaces['name_to_symbol'], name, symbol)
            
            await pipeline.execute()
            
        except Exception as e:
            self.logger.error(f"종목 매핑 저장 실패 [{symbol}:{name}]: {e}")
            raise
    
    async def get_symbol_name(self, symbol: str) -> Optional[str]:
        """종목코드로 종목명 조회"""
        try:
            return await self.redis_client.hget(self.namespaces['symbol_to_name'], symbol)
        except Exception as e:
            self.logger.error(f"종목명 조회 실패 [{symbol}]: {e}")
            return None
    
    async def get_name_symbol(self, name: str) -> Optional[str]:
        """종목명으로 종목코드 조회"""
        try:
            return await self.redis_client.hget(self.namespaces['name_to_symbol'], name)
        except Exception as e:
            self.logger.error(f"종목코드 조회 실패 [{name}]: {e}")
            return None
    
    async def search_symbols(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        """종목 검색 (종목명 또는 종목코드)"""
        try:
            results = []
            
            # 종목코드로 검색
            symbol_to_name = await self.redis_client.hgetall(self.namespaces['symbol_to_name'])
            for symbol, name in symbol_to_name.items():
                if query.upper() in symbol.upper() or query in name:
                    results.append({"symbol": symbol, "name": name})
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            self.logger.error(f"종목 검색 실패 [{query}]: {e}")
            return []
    
    async def bulk_set_symbol_mappings(self, mappings: Dict[str, str]) -> None:
        """종목 매핑 일괄 저장"""
        try:
            with LogContext(self.logger, f"종목 매핑 일괄 저장", count=len(mappings)) as ctx:
                pipeline = self.redis_client.pipeline()
                
                for symbol, name in mappings.items():
                    pipeline.hset(self.namespaces['symbol_to_name'], symbol, name)
                    pipeline.hset(self.namespaces['name_to_symbol'], name, symbol)
                
                await pipeline.execute()
                ctx.log_progress(f"{len(mappings)}개 종목 매핑 저장 완료")
                
        except Exception as e:
            self.logger.error(f"종목 매핑 일괄 저장 실패: {e}")
            raise
    
    # ===========================================
    # 실시간 데이터 캐싱
    # ===========================================
    
    async def set_realtime_data(self, symbol: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """실시간 데이터 저장"""
        try:
            key = f"{self.namespaces['realtime']}:{symbol}"
            
            # Decimal을 문자열로 변환
            serialized_data = self._serialize_data(data)
            
            await self.redis_client.setex(
                key,
                ttl or self.settings.CACHE_TTL_REALTIME,
                json.dumps(serialized_data, ensure_ascii=False)
            )
            
        except Exception as e:
            self.logger.error(f"실시간 데이터 저장 실패 [{symbol}]: {e}")
            raise
    
    async def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """실시간 데이터 조회"""
        try:
            key = f"{self.namespaces['realtime']}:{symbol}"
            data = await self.redis_client.get(key)
            
            if data:
                return self._deserialize_data(json.loads(data))
            return None
            
        except Exception as e:
            self.logger.error(f"실시간 데이터 조회 실패 [{symbol}]: {e}")
            return None
    
    async def bulk_set_realtime_data(self, data_dict: Dict[str, Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """실시간 데이터 일괄 저장"""
        try:
            pipeline = self.redis_client.pipeline()
            
            for symbol, data in data_dict.items():
                key = f"{self.namespaces['realtime']}:{symbol}"
                serialized_data = self._serialize_data(data)
                
                pipeline.setex(
                    key,
                    ttl or self.settings.CACHE_TTL_REALTIME,
                    json.dumps(serialized_data, ensure_ascii=False)
                )
            
            await pipeline.execute()
            
        except Exception as e:
            self.logger.error(f"실시간 데이터 일괄 저장 실패: {e}")
            raise
    
    async def get_multiple_realtime_data(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """다중 실시간 데이터 조회"""
        try:
            if not symbols:
                return {}
            
            keys = [f"{self.namespaces['realtime']}:{symbol}" for symbol in symbols]
            data_list = await self.redis_client.mget(keys)
            
            result = {}
            for symbol, data in zip(symbols, data_list):
                if data:
                    result[symbol] = self._deserialize_data(json.loads(data))
                else:
                    result[symbol] = None
            
            return result
            
        except Exception as e:
            self.logger.error(f"다중 실시간 데이터 조회 실패: {e}")
            return {symbol: None for symbol in symbols}
    
    # ===========================================
    # ETF 구성종목 캐싱
    # ===========================================
    
    async def set_etf_components(self, etf_code: str, components: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """ETF 구성종목 저장"""
        try:
            key = f"{self.namespaces['etf_components']}:{etf_code}"
            serialized_data = self._serialize_data(components)
            
            await self.redis_client.setex(
                key,
                ttl or self.settings.CACHE_TTL_ETF,
                json.dumps(serialized_data, ensure_ascii=False)
            )
            
            self.logger.info(f"ETF 구성종목 캐시 저장: {etf_code} ({len(components)}개)")
            
        except Exception as e:
            self.logger.error(f"ETF 구성종목 저장 실패 [{etf_code}]: {e}")
            raise
    
    async def get_etf_components(self, etf_code: str) -> Optional[List[Dict[str, Any]]]:
        """ETF 구성종목 조회"""
        try:
            key = f"{self.namespaces['etf_components']}:{etf_code}"
            data = await self.redis_client.get(key)
            
            if data:
                return self._deserialize_data(json.loads(data))
            return None
            
        except Exception as e:
            self.logger.error(f"ETF 구성종목 조회 실패 [{etf_code}]: {e}")
            return None
    
    # ===========================================
    # 시장 상태 캐싱
    # ===========================================
    
    async def set_market_status(self, market: str, status_data: Dict[str, Any], ttl: int = 300) -> None:
        """시장 상태 저장"""
        try:
            key = f"{self.namespaces['market_status']}:{market}"
            serialized_data = self._serialize_data(status_data)
            
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(serialized_data, ensure_ascii=False)
            )
            
        except Exception as e:
            self.logger.error(f"시장 상태 저장 실패 [{market}]: {e}")
            raise
    
    async def get_market_status(self, market: str) -> Optional[Dict[str, Any]]:
        """시장 상태 조회"""
        try:
            key = f"{self.namespaces['market_status']}:{market}"
            data = await self.redis_client.get(key)
            
            if data:
                return self._deserialize_data(json.loads(data))
            return None
            
        except Exception as e:
            self.logger.error(f"시장 상태 조회 실패 [{market}]: {e}")
            return None
    
    # ===========================================
    # 시장 지수 캐싱
    # ===========================================
    
    async def set_market_indices(self, indices_data: Dict[str, Any], ttl: int = 1800) -> None:
        """
        시장 지수 정보 저장 (코스피, 코스닥)
        
        Args:
            indices_data: 시장 지수 데이터
            ttl: 캐시 만료 시간 (기본 30분)
        """
        try:
            key = "market:indices"
            serialized_data = self._serialize_data(indices_data)
            
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(serialized_data, ensure_ascii=False)
            )
            
            self.logger.info(f"시장 지수 정보 캐시 저장: {len(indices_data)}개")
            
        except Exception as e:
            self.logger.error(f"시장 지수 저장 실패: {e}")
            raise
    
    async def get_market_indices(self) -> Optional[Dict[str, Any]]:
        """시장 지수 정보 조회"""
        try:
            key = "market:indices"
            data = await self.redis_client.get(key)
            
            if data:
                return self._deserialize_data(json.loads(data))
            return None
            
        except Exception as e:
            self.logger.error(f"시장 지수 조회 실패: {e}")
            return None
    
    # ===========================================
    # 통계 및 메타데이터
    # ===========================================
    
    async def increment_api_call_count(self, api_name: str, window: str = "hour") -> int:
        """API 호출 횟수 증가 및 반환"""
        try:
            now = datetime.now()
            
            if window == "hour":
                key_suffix = now.strftime("%Y%m%d%H")
                ttl = 3600  # 1시간
            elif window == "minute":
                key_suffix = now.strftime("%Y%m%d%H%M")
                ttl = 60  # 1분
            else:  # day
                key_suffix = now.strftime("%Y%m%d")
                ttl = 86400  # 1일
            
            key = f"{self.namespaces['stats']}:api_calls:{api_name}:{key_suffix}"
            
            pipeline = self.redis_client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, ttl)
            
            results = await pipeline.execute()
            return results[0]
            
        except Exception as e:
            self.logger.error(f"API 호출 카운트 증가 실패 [{api_name}]: {e}")
            return 0
    
    async def get_api_call_count(self, api_name: str, window: str = "hour") -> int:
        """API 호출 횟수 조회"""
        try:
            now = datetime.now()
            
            if window == "hour":
                key_suffix = now.strftime("%Y%m%d%H")
            elif window == "minute":
                key_suffix = now.strftime("%Y%m%d%H%M")
            else:  # day
                key_suffix = now.strftime("%Y%m%d")
            
            key = f"{self.namespaces['stats']}:api_calls:{api_name}:{key_suffix}"
            count = await self.redis_client.get(key)
            
            return int(count) if count else 0
            
        except Exception as e:
            self.logger.error(f"API 호출 카운트 조회 실패 [{api_name}]: {e}")
            return 0
    
    # ===========================================
    # 유틸리티 메서드
    # ===========================================
    
    def _serialize_data(self, data: Any) -> Any:
        """데이터 직렬화 (Decimal -> str 변환)"""
        if isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data
    
    def _deserialize_data(self, data: Any) -> Any:
        """데이터 역직렬화 (str -> 적절한 타입 변환)"""
        if isinstance(data, dict):
            return {k: self._deserialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._deserialize_data(item) for item in data]
        else:
            return data
    
    async def clear_cache(self, pattern: str) -> int:
        """패턴에 맞는 캐시 삭제"""
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted_count = await self.redis_client.delete(*keys)
                self.logger.info(f"캐시 삭제 완료: {deleted_count}개 키 ({pattern})")
                return deleted_count
            
            return 0
            
        except Exception as e:
            self.logger.error(f"캐시 삭제 실패 [{pattern}]: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        try:
            info = await self.redis_client.info()
            
            # 네임스페이스별 키 개수
            namespace_counts = {}
            for namespace_name, namespace_key in self.namespaces.items():
                count = 0
                async for _ in self.redis_client.scan_iter(match=f"{namespace_key}:*"):
                    count += 1
                namespace_counts[namespace_name] = count
            
            return {
                "redis_info": {
                    "used_memory": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses")
                },
                "namespace_counts": namespace_counts,
                "total_keys": sum(namespace_counts.values())
            }
            
        except Exception as e:
            self.logger.error(f"캐시 통계 조회 실패: {e}")
            return {}
    
    async def cleanup_expired_cache(self) -> Dict[str, int]:
        """
        만료된 캐시 정리
        
        Returns:
            Dict[str, int]: 정리 결과 통계
        """
        try:
            self.logger.info("만료된 캐시 정리 시작")
            
            # Redis의 expired key 정리는 자동으로 처리되므로 
            # 여기서는 통계 정보만 수집
            info = await self.redis_client.info()
            
            expired_keys = info.get("expired_keys", 0)
            evicted_keys = info.get("evicted_keys", 0)
            
            result = {
                "expired_keys": expired_keys,
                "evicted_keys": evicted_keys,
                "cleanup_time": int(datetime.now().timestamp())
            }
            
            self.logger.info(f"캐시 정리 완료: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"캐시 정리 실패: {e}")
            return {"expired_keys": 0, "evicted_keys": 0, "cleanup_time": 0}

    async def clear_realtime_cache(self) -> int:
        """
        실시간 데이터 캐시 전체 삭제
        
        Returns:
            int: 삭제된 키 개수
        """
        try:
            pattern = f"{self.namespaces['realtime']}:*"
            return await self.clear_cache(pattern)
            
        except Exception as e:
            self.logger.error(f"실시간 캐시 삭제 실패: {e}")
            return 0 