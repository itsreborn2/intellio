"""
pykrx를 이용한 ETF 구성종목 크롤링 서비스
"""
import asyncio
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import pandas as pd

from pykrx import stock
from pydantic import BaseModel
from loguru import logger

from stockeasy.collector.core.config import get_settings

settings = get_settings()


class ETFComponent(BaseModel):
    """ETF 구성종목 정보"""
    etf_code: str
    stock_code: str
    stock_name: str
    weight: float
    quantity: int
    market_value: float
    updated_date: str


class ETFInfo(BaseModel):
    """ETF 기본 정보"""
    code: str
    name: str
    market: str
    sector: str
    net_asset_value: Optional[float] = None
    total_market_cap: Optional[float] = None


class ETFCrawler:
    """ETF 구성종목 크롤링 서비스"""
    
    def __init__(self):
                # 주요 ETF 목록 (CSV 파일 기반으로 확장)
        self.major_etfs = {
            # 마켓
            "069500": "KODEX 200",
            "229200": "KODEX 코스닥150",
            
            # 방산/우주항공
            "449450": "PLUS K방산",
            "421320": "PLUS 우주항공&UAM",
            
            # 기타 (엔터, 게임, 로봇)
            "228810": "TIGER 미디어컨텐츠",
            "228800": "TIGER 여행레저",
            "475050": "ACE KPOP포커스",
            "364990": "TIGER 게임TOP10",
            "445290": "KODEX K-로봇액티브",
            
            # 통신
            "098560": "TIGER 방송통신",
            "157490": "TIGER 소프트웨어",
            "365000": "TIGER 인터넷TOP10",
            
            # 헬스케어/바이오
            "460280": "KIWOOM Fn유전자혁신기술",
            "261070": "TIGER 코스닥150바이오테크",
            "463050": "TIMEFOLIO K바이오액티브",
            "483020": "KIWOOM 의료AI",
            "227540": "TIGER 200 헬스케어",
            "464610": "SOL 의료기기소부장Fn",
            
            # 전력기기/에너지
            "433500": "ACE 원자력테마딥서치",
            "487240": "KODEX AI전력핵심설비",
            "457990": "PLUS 태양광&ESS",
            
            # 금융/보험
            "102970": "KODEX 증권",
            "139270": "TIGER 200 금융",
            "091170": "KODEX 은행",
            "140700": "KODEX 보험",
            
            # 철강/화학/금속
            "139250": "TIGER 200 에너지화학",
            "139240": "TIGER 200 철강소재",
            
            # 건설
            "139220": "TIGER 200 건설",
            
            # 소비재/음식료
            "479850": "HANARO K-뷰티",
            "438900": "HANARO Fn K-푸드",
            "228790": "TIGER 화장품",
            
            # 2차전지
            "455860": "SOL 2차전지소부장Fn",
            "364980": "TIGER 2차전지TOP10",
            
            # 자동차
            "091180": "KODEX 자동차",
            "464600": "SOL 자동차소부장Fn",
            
            # 조선/운송
            "466920": "SOL 조선TOP3플러스",
            "140710": "KODEX 운송",
            
            # 반도체
            "475300": "SOL 반도체전공정",
            "091160": "KODEX 반도체",
            "475310": "SOL 반도체후공정",
        }
        
        logger.info("ETF 크롤러 초기화 완료")
    
    async def get_all_etf_list(self) -> List[ETFInfo]:
        """전체 ETF 목록 조회"""
        try:
            logger.info("전체 ETF 목록 조회 시작")
            
            # pykrx는 동기 함수이므로 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            etf_df = await loop.run_in_executor(None, stock.get_etf_ticker_list)
            
            etf_list = []
            for ticker in etf_df:
                try:
                    # ETF 기본 정보 조회
                    name = await loop.run_in_executor(
                        None, 
                        lambda: stock.get_etf_ticker_name(ticker)
                    )
                    
                    etf_info = ETFInfo(
                        code=ticker,
                        name=name,
                        market="KRX",
                        sector="ETF"
                    )
                    etf_list.append(etf_info)
                    
                except Exception as e:
                    logger.warning(f"ETF 정보 조회 실패 ({ticker}): {e}")
                    continue
            
            logger.info(f"전체 ETF 목록 조회 완료: {len(etf_list)}개")
            return etf_list
            
        except Exception as e:
            logger.error(f"전체 ETF 목록 조회 실패: {e}")
            return []
    
    async def get_etf_components(
        self, 
        etf_code: str, 
        date_str: Optional[str] = None
    ) -> List[ETFComponent]:
        """특정 ETF 구성종목 조회"""
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y%m%d")
            
            logger.debug(f"ETF 구성종목 조회: {etf_code} ({date_str})")
            
            # pykrx는 동기 함수이므로 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            
            # ETF 구성종목 조회
            components_df = await loop.run_in_executor(
                None,
                lambda: stock.get_etf_portfolio_deposit_file(etf_code)
            )
            
            if components_df is None or components_df.empty:
                logger.warning(f"ETF 구성종목 데이터 없음: {etf_code}")
                return []
            
            components = []
            for ticker, row in components_df.iterrows():
                try:
                    # 종목명 조회 (별도 API 호출 필요)
                    stock_name = ""
                    try:
                        stock_name = await loop.run_in_executor(
                            None,
                            lambda: stock.get_market_ticker_name(ticker)
                        )
                        # DataFrame이 반환되는 경우 처리
                        if hasattr(stock_name, 'empty'):
                            stock_name = ""
                    except Exception as e:
                        logger.debug(f"종목명 조회 실패 ({ticker}): {e}")
                        pass  # 종목명 조회 실패 시 빈 문자열 유지
                    
                    component = ETFComponent(
                        etf_code=etf_code,
                        stock_code=ticker,  # 인덱스가 종목코드
                        stock_name=stock_name,
                        weight=float(row.get('비중', 0.0)),
                        quantity=int(row.get('계약수', 0)),
                        market_value=float(row.get('금액', 0.0)),
                        updated_date=date_str
                    )
                    components.append(component)
                    
                except Exception as e:
                    logger.warning(f"구성종목 파싱 실패 ({etf_code}, {ticker}): {e}")
                    continue
            
            logger.info(f"ETF 구성종목 조회 완료: {etf_code} - {len(components)}개")
            return components
            
        except Exception as e:
            logger.error(f"ETF 구성종목 조회 실패 ({etf_code}): {e}")
            return []
    
    async def get_multiple_etf_components(
        self, 
        etf_codes: List[str], 
        date_str: Optional[str] = None
    ) -> Dict[str, List[ETFComponent]]:
        """여러 ETF 구성종목 일괄 조회"""
        logger.info(f"ETF 구성종목 일괄 조회 시작: {len(etf_codes)}개 ETF")
        
        results = {}
        for etf_code in etf_codes:
            try:
                components = await self.get_etf_components(etf_code, date_str)
                results[etf_code] = components
                
                # API 호출 간격 조절 (pykrx 서버 부하 방지)
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"ETF 구성종목 조회 실패 ({etf_code}): {e}")
                results[etf_code] = []
                continue
        
        total_components = sum(len(components) for components in results.values())
        logger.info(f"ETF 구성종목 일괄 조회 완료: {len(results)}개 ETF, {total_components}개 구성종목")
        
        return results
    
    async def get_major_etf_components(
        self, 
        date_str: Optional[str] = None
    ) -> Dict[str, List[ETFComponent]]:
        """주요 ETF 구성종목 조회"""
        logger.info("주요 ETF 구성종목 조회 시작")
        
        etf_codes = list(self.major_etfs.keys())
        return await self.get_multiple_etf_components(etf_codes, date_str)
    
    async def get_etf_price_info(self, etf_code: str, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """ETF 가격 정보 조회"""
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y%m%d")
            
            logger.debug(f"ETF 가격 정보 조회: {etf_code} ({date_str})")
            
            loop = asyncio.get_event_loop()
            
            # ETF OHLCV 데이터 조회
            price_df = await loop.run_in_executor(
                None,
                lambda: stock.get_etf_ohlcv_by_date(date_str, date_str, etf_code)
            )
            
            if price_df is None or price_df.empty:
                return None
            
            # 최신 데이터 (보통 하나의 행)
            latest = price_df.iloc[-1]
            
            return {
                "date": date_str,
                "open": float(latest.get('시가', 0)),
                "high": float(latest.get('고가', 0)),
                "low": float(latest.get('저가', 0)),
                "close": float(latest.get('종가', 0)),
                "volume": int(latest.get('거래량', 0)),
                "trading_value": float(latest.get('거래대금', 0)),
                "nav": float(latest.get('기초지수', 0)) if '기초지수' in latest else None,
            }
            
        except Exception as e:
            logger.error(f"ETF 가격 정보 조회 실패 ({etf_code}): {e}")
            return None
    
    async def get_etf_historical_data(
        self, 
        etf_code: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """ETF 과거 데이터 조회"""
        try:
            logger.debug(f"ETF 과거 데이터 조회: {etf_code} ({start_date}~{end_date})")
            
            loop = asyncio.get_event_loop()
            
            # ETF 과거 OHLCV 데이터 조회
            price_df = await loop.run_in_executor(
                None,
                lambda: stock.get_etf_ohlcv_by_date(start_date, end_date, etf_code)
            )
            
            if price_df is None or price_df.empty:
                return []
            
            results = []
            for date_idx, row in price_df.iterrows():
                data = {
                    "date": date_idx.strftime("%Y%m%d"),
                    "open": float(row.get('시가', 0)),
                    "high": float(row.get('고가', 0)),
                    "low": float(row.get('저가', 0)),
                    "close": float(row.get('종가', 0)),
                    "volume": int(row.get('거래량', 0)),
                    "trading_value": float(row.get('거래대금', 0)),
                }
                results.append(data)
            
            logger.info(f"ETF 과거 데이터 조회 완료: {etf_code} - {len(results)}일")
            return results
            
        except Exception as e:
            logger.error(f"ETF 과거 데이터 조회 실패 ({etf_code}): {e}")
            return []
    
    async def update_all_etf_components(self) -> Dict[str, int]:
        """모든 주요 ETF 구성종목 업데이트"""
        logger.info("모든 주요 ETF 구성종목 업데이트 시작")
        
        try:
            # 주요 ETF 구성종목 조회
            components_data = await self.get_major_etf_components()
            
            results = {}
            for etf_code, components in components_data.items():
                results[etf_code] = len(components)
                
                if components:
                    etf_name = self.major_etfs.get(etf_code, etf_code)
                    logger.info(f"ETF 구성종목 업데이트 완료: {etf_name}({etf_code}) - {len(components)}개")
                else:
                    logger.warning(f"ETF 구성종목 데이터 없음: {etf_code}")
            
            total_components = sum(results.values())
            logger.info(f"모든 주요 ETF 구성종목 업데이트 완료: {len(results)}개 ETF, {total_components}개 구성종목")
            
            return results
            
        except Exception as e:
            logger.error(f"ETF 구성종목 업데이트 실패: {e}")
            return {}
    
    def get_major_etf_list(self) -> Dict[str, str]:
        """주요 ETF 목록 반환"""
        return self.major_etfs.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """크롤러 통계"""
        return {
            "major_etf_count": len(self.major_etfs),
            "supported_markets": ["KRX"],
            "data_source": "pykrx",
        } 