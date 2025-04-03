"""
종목 정보 서비스 클래스

이 모듈은 종목 코드 및 이름을 관리하고 조회하기 위한 서비스를 제공합니다.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from common.core.config import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class StockInfoService:
    """종목 정보 서비스 클래스"""
    
    def __init__(self):
        """서비스 초기화"""
        # 종목 정보 캐시 경로
        self.cache_dir = Path(settings.LOCAL_CACHE_DIR)
        self.stock_info_path = self.cache_dir / "stock_info.json"
        
        # 캐시 디렉토리 생성
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 종목 정보 캐시
        self._stock_info_cache = None
        self._last_cache_update = None
        
        # 캐시 만료 시간 (24시간)
        self.cache_expiry_seconds = 24 * 60 * 60
        
    async def get_stock_by_code(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        종목 코드로 종목 정보를 조회합니다.
        
        Args:
            stock_code: 종목 코드
            
        Returns:
            종목 정보를 포함하는 딕셔너리 또는 None
        """
        stock_info = await self._load_stock_info()
        if not stock_info:
            return None
            
        # 코드로 조회
        code_map = stock_info.get("by_code", {})
        return code_map.get(stock_code)
        
    async def get_stock_by_name(self, stock_name: str) -> Optional[Dict[str, Any]]:
        """
        종목명으로 종목 정보를 조회합니다.
        
        Args:
            stock_name: 종목명
            
        Returns:
            종목 정보를 포함하는 딕셔너리 또는 None
        """
        stock_info = await self._load_stock_info()
        if not stock_info:
            return None
            
        # 이름으로 조회 (정확한 일치)
        name_map = stock_info.get("by_name", {})
        if stock_name in name_map:
            return name_map.get(stock_name)
            
        # 부분 일치 검색
        for name, info in name_map.items():
            if stock_name in name:
                return info
                
        return None
        
    async def search_stocks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        종목을 검색합니다.
        
        Args:
            query: 검색어 (종목명 또는 종목코드)
            limit: 최대 결과 수
            
        Returns:
            검색 결과 목록
        """
        stock_info = await self._load_stock_info()
        if not stock_info:
            return []
            
        results = []
        name_map = stock_info.get("by_name", {})
        
        # 종목코드 검색
        if query.isdigit():
            code_map = stock_info.get("by_code", {})
            if query in code_map:
                results.append(code_map[query])
                
        # 종목명 검색 (부분 일치)
        for name, info in name_map.items():
            if query.lower() in name.lower():
                if info not in results:  # 중복 방지
                    results.append(info)
                    
            if len(results) >= limit:
                break
                
        return results
        
    async def _load_stock_info(self) -> Dict[str, Any]:
        """
        종목 정보를 로드합니다. 캐시가 있으면 캐시를 사용하고, 없으면 DB에서 조회합니다.
        
        Returns:
            종목 정보 딕셔너리
        """
        # 캐시가 이미 로드되었고 만료되지 않았는지 확인
        now = datetime.now()
        if (self._stock_info_cache is not None and 
            self._last_cache_update is not None and 
            (now - self._last_cache_update).total_seconds() < self.cache_expiry_seconds):
            return self._stock_info_cache
            
        # 캐시 파일이 있는지 확인
        if os.path.exists(self.stock_info_path):
            try:
                # 캐시 파일의 수정 시간 확인
                mtime = os.path.getmtime(self.stock_info_path)
                file_age = now.timestamp() - mtime
                
                # 캐시가 유효하면 로드
                if file_age < self.cache_expiry_seconds:
                    with open(self.stock_info_path, 'r', encoding='utf-8') as f:
                        self._stock_info_cache = json.load(f)
                        self._last_cache_update = now
                        logger.info("Loaded stock info from cache file")
                        return self._stock_info_cache
            except Exception as e:
                logger.warning(f"Failed to load stock info cache: {str(e)}")
        
        # 캐시가 없거나 만료되었으면 DB에서 조회
        stock_info = await self._fetch_stock_info_from_db()
        
        # 캐시 업데이트
        self._stock_info_cache = stock_info
        self._last_cache_update = now
        
        # 캐시 파일 저장
        try:
            with open(self.stock_info_path, 'w', encoding='utf-8') as f:
                json.dump(stock_info, f, ensure_ascii=False, indent=2)
                logger.info("Updated stock info cache file")
        except Exception as e:
            logger.warning(f"Failed to save stock info cache: {str(e)}")
            
        return stock_info
        
    async def _fetch_stock_info_from_db(self, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        DB에서 종목 정보를 조회합니다.
        
        Args:
            db: DB 세션 (없으면 새로 생성)
            
        Returns:
            종목 정보 딕셔너리
        """
        # 여기서는 간단한 샘플 데이터를 반환
        # 실제 구현에서는 DB에서 조회하도록 수정 필요
        sample_data = {
            "by_code": {
                "005930": {
                    "code": "005930",
                    "name": "삼성전자",
                    "market": "KOSPI",
                    "sector": "전기·전자"
                },
                "035420": {
                    "code": "035420",
                    "name": "NAVER",
                    "market": "KOSPI",
                    "sector": "서비스업"
                },
                "035720": {
                    "code": "035720",
                    "name": "카카오",
                    "market": "KOSPI",
                    "sector": "서비스업"
                }
            },
            "by_name": {
                "삼성전자": {
                    "code": "005930",
                    "name": "삼성전자",
                    "market": "KOSPI",
                    "sector": "전기·전자"
                },
                "NAVER": {
                    "code": "035420",
                    "name": "NAVER",
                    "market": "KOSPI",
                    "sector": "서비스업"
                },
                "카카오": {
                    "code": "035720",
                    "name": "카카오",
                    "market": "KOSPI",
                    "sector": "서비스업"
                }
            }
        }
        
        # TODO: DB에서 종목 정보 조회 구현
        
        return sample_data 