"""
종목 정보 서비스 클래스

이 모듈은 종목 코드 및 이름을 관리하고 조회하기 위한 서비스를 제공합니다.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

import pandas as pd

from common.core.config import settings


logger = logging.getLogger(__name__)

class StockInfoService:
    """종목 정보 서비스 클래스"""
    _instance = None
    _stock_info_cache = None  # 메모리 캐시
    _last_update_date = None  # 마지막 업데이트 날짜
    _update_task = None  # 자동 업데이트 태스크
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            asyncio.create_task(cls._instance._initialize())
        return cls._instance
    
    async def _initialize(self):
        """서비스 초기화"""
        logger.info("주식 정보 서비스 초기화 시작")
        
        # 종목 정보 캐시 경로
        self.cache_dir = Path(settings.STOCKEASY_LOCAL_CACHE_DIR)
        self.stock_info_path = self.cache_dir / "stock_info.json"
        
        # 캐시 디렉토리 생성
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 초기 데이터 로드
        try:
            # 1. 파일 캐시 확인
            if os.path.exists(self.stock_info_path):
                with open(self.stock_info_path, 'r', encoding='utf-8') as f:
                    self._stock_info_cache = json.load(f)
                    logger.info("캐시 파일에서 초기 주식 정보 로드 완료")
            
            # 2. 파일 캐시가 없으면 KRX에서 조회
            if self._stock_info_cache is None:
                logger.info("캐시 파일이 없어 KRX에서 초기 데이터를 가져옵니다")
                self._stock_info_cache = await self._fetch_stock_info_from_krx()
                
                # 파일 캐시 저장
                with open(self.stock_info_path, 'w', encoding='utf-8') as f:
                    json.dump(self._stock_info_cache, f, ensure_ascii=False, indent=2)
                    logger.info("초기 주식 정보 캐시 파일 생성 완료")
            
            self._last_update_date = datetime.now().date()
            
        except Exception as e:
            logger.error(f"초기 주식 정보 로드 실패: {str(e)}")
            self._stock_info_cache = {"by_code": {}, "by_name": {}}
            self._last_update_date = datetime.now().date()
        
        # 자동 업데이트 태스크 시작
        self._update_task = asyncio.create_task(self._start_auto_update())
        logger.info("주식 정보 서비스 초기화 완료")
        stocks = await self.search_stocks("삼성전", limit=5)
        for i, stock in enumerate(stocks):
            print(f"[{i+1}] 종목명: {stock['name']}, 종목코드: {stock['code']}, 업종: {stock['sector']}")
        
    async def _start_auto_update(self):
        """자동 업데이트 태스크를 시작합니다."""
        logger.info("주식 정보 자동 업데이트 태스크 시작")
        while True:
            try:
                now = datetime.now()
                target_time = now.replace(hour=7, minute=30, second=0, microsecond=0)
                
                # 이미 7:30을 지났다면 다음 날 7:30으로 설정
                if now >= target_time:
                    target_time = target_time + timedelta(days=1)
                
                # 다음 업데이트까지 대기
                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"다음 주식 정보 업데이트 예정 시각: {target_time}")
                await asyncio.sleep(wait_seconds)
                
                # 7:30이 되면 데이터 갱신
                logger.info("예정된 시각에 주식 정보 업데이트 시작")
                stock_info = await self._fetch_stock_info_from_krx()
                self._stock_info_cache = stock_info
                self._last_update_date = datetime.now().date()
                
                # 파일 캐시 업데이트
                try:
                    with open(self.stock_info_path, 'w', encoding='utf-8') as f:
                        json.dump(stock_info, f, ensure_ascii=False, indent=2)
                        logger.info("주식 정보 캐시 파일 업데이트 완료")
                except Exception as e:
                    logger.warning(f"주식 정보 캐시 파일 저장 실패: {str(e)}")
                    
            except Exception as e:
                logger.error(f"자동 업데이트 태스크 오류 발생: {str(e)}")
                await asyncio.sleep(60)  # 에러 발생시 1분 후 재시도
    
    async def read_krx_code(self):
        # 상장 종목 목록 가져오기 
        #url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType=kosdaqMkt'
        #url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType=stockMkt'
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        krx = pd.read_html(url, encoding='euc-kr', header=0)[0]
        # 데이터 정리
        krx = krx[['종목코드','회사명', '업종']]
        krx = krx.rename(columns={'종목코드':'code','회사명':'name'})
        krx.code = krx.code.map('{:06d}'.format)
        krx = krx[~krx["name"].str.contains("스팩")]
        #krx.to_csv(f"listed_company.csv",index=False,  encoding="utf-8-sig")
        df1 = pd.DataFrame({'code':['KOSPI','KOSDAQ'],
                    'name':['KOSPI','KOSDAQ'],
                    '업종':['KOSPI','KOSDAQ']})
        
        krx = pd.concat([krx, df1], ignore_index=True)
        # idx = krx["name"].isin(["스팩"])
        # count = len(idx)
        #sToday = dtNow.strftime('%Y%m%d')
        #krx.to_csv(f"listed_company.csv",index=False,  encoding="utf-8-sig")
        return krx
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
        종목 정보를 로드합니다. 
        메모리에 캐시된 데이터를 반환합니다.
        
        Returns:
            종목 정보 딕셔너리
        """
        return self._stock_info_cache or {"by_code": {}, "by_name": {}}
        
    async def _fetch_stock_info_from_krx(self) -> Dict[str, Any]:
        """
        KRX에서 종목 정보를 조회합니다.
        
        Returns:
            종목 정보 딕셔너리
        """
        try:
            # KRX에서 종목 정보 조회
            krx_data = await self.read_krx_code()
            
            # 데이터 변환
            by_code = {}
            by_name = {}
            
            for _, row in krx_data.iterrows():
                stock_info = {
                    "code": row["code"],
                    "name": row["name"],
                    "sector": row["업종"]
                }
                
                by_code[row["code"]] = stock_info
                by_name[row["name"]] = stock_info
            
            return {
                "by_code": by_code,
                "by_name": by_name
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch stock info from KRX: {str(e)}")
            return {"by_code": {}, "by_name": {}}