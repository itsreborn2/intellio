"""
의존성 주입 모듈
"""
from fastapi import HTTPException

from stockeasy.collector.services.data_collector import DataCollectorService
from stockeasy.collector.services.cache_manager import CacheManager

# 전역 서비스 인스턴스
_data_collector: DataCollectorService = None
_cache_manager: CacheManager = None


def set_data_collector(collector: DataCollectorService):
    """데이터 수집 서비스 인스턴스 설정"""
    global _data_collector
    _data_collector = collector


def set_cache_manager(manager: CacheManager):
    """캐시 매니저 인스턴스 설정"""
    global _cache_manager
    _cache_manager = manager


def get_data_collector() -> DataCollectorService:
    """데이터 수집 서비스 인스턴스 반환"""
    if not _data_collector:
        raise HTTPException(status_code=503, detail="데이터 수집 서비스가 초기화되지 않았습니다.")
    return _data_collector


def get_cache_manager() -> CacheManager:
    """캐시 매니저 인스턴스 반환"""
    if not _cache_manager:
        raise HTTPException(status_code=503, detail="캐시 매니저가 초기화되지 않았습니다.")
    return _cache_manager 