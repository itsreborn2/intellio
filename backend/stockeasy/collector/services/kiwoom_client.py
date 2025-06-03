"""
키움증권 REST API 클라이언트
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal

import aiohttp
import requests
from pydantic import BaseModel
from loguru import logger

from stockeasy.collector.core.config import get_settings

settings = get_settings()


class KiwoomTokenResponse(BaseModel):
    """키움 API 토큰 응답"""
    token: str  # access_token 대신 token
    token_type: str
    expires_dt: str  # expires_in 대신 expires_dt (만료 일시)
    return_code: int
    return_msg: str


class KiwoomErrorResponse(BaseModel):
    """키움 API 에러 응답"""
    return_code: int
    return_msg: str


class KiwoomStockInfo(BaseModel):
    """키움 주식 기본정보"""
    stk_cd: str  # 종목코드
    stk_nm: str  # 종목명
    mkt_gb: str  # 시장구분
    stk_gb: str  # 종목구분
    lst_dt: Optional[str] = None  # 상장일
    stk_cnt: Optional[str] = None  # 총주식수
    par_pr: Optional[str] = None  # 액면가


class KiwoomStockListItem(BaseModel):
    """키움 주식 리스트 아이템 (ka10099 응답) - 실제 API 응답 구조에 맞게 수정"""
    code: str  # 종목코드 (실제 응답에서는 code 필드)
    name: str  # 종목명 (실제 응답에서는 name 필드)
    
    # 실제 응답에 포함된 추가 필드들 (선택적)
    listCount: Optional[str] = None  # 상장주식수
    auditInfo: Optional[str] = None  # 감리구분
    regDay: Optional[str] = None     # 등록일
    lastPrice: Optional[str] = None  # 현재가
    state: Optional[str] = None      # 상태
    marketCode: Optional[str] = None # 시장코드
    marketName: Optional[str] = None # 시장명


class KiwoomStockListResponse(BaseModel):
    """키움 주식 리스트 응답"""
    output: List[KiwoomStockListItem]
    response_headers: Dict[str, str]


class KiwoomSupplyDemand(BaseModel):
    """키움 수급데이터"""
    dt: str  # 일자
    stk_cd: str  # 종목코드
    frg_amt: Optional[str] = None  # 외국인 금액
    ins_amt: Optional[str] = None  # 기관 금액
    pns_amt: Optional[str] = None  # 개인 금액


class KiwoomAPIClient:
    """키움증권 REST API 클라이언트"""
    
    def __init__(self):
        self.host = "https://api.kiwoom.com"  # 실전투자
        # self.host = "https://mockapi.kiwoom.com"  # 모의투자
        
        self.app_key = settings.KIWOOM_APP_KEY
        self.secret_key = settings.KIWOOM_SECRET_KEY
        
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._auth_failed = False  # 인증 실패 플래그
        
        # API 호출 제한 관리
        self.semaphore = asyncio.Semaphore(settings.MAX_API_CALLS_PER_SECOND)
        self.last_request_time = 0
        self.request_count = 0
        
        # 전체 종목 리스트 캐시
        self._all_stocks_cache: Dict[str, Dict[str, str]] = {}
        self._last_stock_update: Optional[datetime] = None

        # stock ai 종목리스트 캐시
        self._stockai_stocks_cache: Dict[str, Dict[str, str]] = {}
        self._last_stockai_update: Optional[datetime] = None
        

        logger.info(f"키움 API 클라이언트 초기화 완료 : {self.app_key}")
    
    async def _ensure_token(self) -> str:
        """토큰 유효성 확인 및 갱신"""
        if self._auth_failed:
            raise Exception("키움 API 인증이 실패했습니다. API 키와 시크릿을 확인해주세요.")
        
        if not self.access_token or (
            self.token_expires_at and datetime.now() >= self.token_expires_at
        ):
            await self._refresh_token()
        
        if not self.access_token:
            raise Exception("키움 API 토큰을 얻을 수 없습니다.")
            
        return self.access_token
    
    async def _refresh_token(self) -> None:
        """접근토큰 발급/갱신"""
        # API 키가 설정되지 않은 경우 에러 발생
        if (not self.app_key or not self.secret_key or
            self.app_key == "your_app_key_here" or 
            self.app_key == "test_api_key"):
            
            error_msg = "키움 API 키가 설정되지 않았습니다. 환경변수를 확인해주세요."
            logger.error(error_msg)
            self._auth_failed = True
            raise Exception(error_msg)
        
        try:
            logger.info("키움 API 토큰 발급 중...")
            
            url = f"{self.host}/oauth2/token"
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
            }
            data = {
                'grant_type': 'client_credentials',
                'appkey': self.app_key,
                'secretkey': self.secret_key,
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    result = await response.json()
                    
                    # 디버그용 응답 로깅
                    logger.info(f"키움 API 응답 상태: {response.status}")
                    logger.info(f"키움 API 응답 데이터: {result}")
                    
                    if response.status == 200:
                        # 성공 응답 확인 - 실제 키움 API는 token 필드 사용
                        if 'token' in result and result.get('return_code') == 0:
                            token_info = KiwoomTokenResponse(**result)
                            
                            self.access_token = token_info.token
                            
                            # expires_dt를 datetime으로 파싱 (예: "20250602004341" -> 2025-06-02 00:43:41)
                            try:
                                expires_dt = datetime.strptime(token_info.expires_dt, "%Y%m%d%H%M%S")
                                # 5분 여유시간 적용
                                self.token_expires_at = expires_dt - timedelta(minutes=5)
                            except ValueError:
                                # 파싱 실패 시 1시간 후 만료로 설정
                                self.token_expires_at = datetime.now() + timedelta(hours=1)
                            
                            logger.info(f"키움 API 토큰 발급 성공 (만료: {self.token_expires_at})")
                            self._auth_failed = False
                        else:
                            # 에러 응답 처리
                            error_msg = f"키움 API 토큰 발급 실패: {result.get('return_msg', '알 수 없는 오류')} (코드: {result.get('return_code', -1)})"
                            logger.error(error_msg)
                            self._auth_failed = True
                            raise Exception(error_msg)
                    else:
                        error_text = await response.text()
                        error_msg = f"키움 API 토큰 발급 실패: HTTP {response.status} - {error_text}"
                        logger.error(error_msg)
                        self._auth_failed = True
                        raise Exception(error_msg)
                        
        except Exception as e:
            logger.error(f"키움 API 토큰 발급 중 오류: {e}")
            self._auth_failed = True
            raise
    
    async def _rate_limit(self) -> None:
        """API 호출 제한 관리"""
        async with self.semaphore:
            current_time = asyncio.get_event_loop().time()
            time_diff = current_time - self.last_request_time
            
            # 초당 제한 확인
            if time_diff < 1.0 / settings.MAX_API_CALLS_PER_SECOND:
                await asyncio.sleep(1.0 / settings.MAX_API_CALLS_PER_SECOND - time_diff)
            
            self.last_request_time = asyncio.get_event_loop().time()
            self.request_count += 1
    
    async def _make_request(
        self,
        api_id: str,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """공통 API 요청 처리"""
        # 인증 실패 시 에러 발생
        if self._auth_failed:
            raise Exception(f"키움 API 인증이 실패했습니다. {api_id} 호출 불가")
        
        await self._rate_limit()
        token = await self._ensure_token()
        
        url = f"{self.host}/api/dostk/stkinfo"
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': api_id,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 실제 API 응답 구조 로깅 (디버깅용)
                        logger.info(f"키움 API 응답 ({api_id}): {result}")
                        
                        # 응답 헤더 정보 추가 (기존 데이터 덮어쓰지 않도록 주의)
                        if 'response_headers' not in result:
                            result['response_headers'] = {
                                'next-key': response.headers.get('next-key', ''),
                                'cont-yn': response.headers.get('cont-yn', 'N'),
                                'api-id': response.headers.get('api-id', api_id)
                            }
                        
                        logger.debug(f"API 호출 성공: {api_id}")
                        return result
                    else:
                        error_text = await response.text()
                        error_msg = f"API 호출 실패 ({api_id}): {response.status} - {error_text}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                        
        except Exception as e:
            error_msg = f"API 요청 중 오류 ({api_id}): {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def get_stock_info(self, symbol: str) -> Optional[KiwoomStockInfo]:
        """주식 기본정보 조회 (ka10001) - 실제 API 응답 구조에 맞게 수정"""
        try:
            logger.info(f"[kiwoom]주식 기본정보 조회: {symbol}")
            
            data = {
                'stk_cd': symbol
            }
            
            result = await self._make_request('ka10001', data)
            
            # 실제 키움 API 응답 구조: 데이터가 루트 레벨에 있음
            # return_code가 0이면 성공
            if result.get('return_code') == 0 and result.get('stk_cd'):
                # 키움 API 응답을 우리가 정의한 KiwoomStockInfo 구조로 변환
                stock_info_data = {
                    'stk_cd': result.get('stk_cd', symbol),
                    'stk_nm': result.get('stk_nm', f'종목_{symbol}'),
                    'mkt_gb': 'KOSPI',  # 기본값, 실제로는 별도 API에서 가져와야 함
                    'stk_gb': 'ST',     # 기본값
                    'lst_dt': result.get('lst_pric', '20100101'),  # 상장일 정보가 없어서 임시
                    'stk_cnt': result.get('flo_stk', '1000000000'),  # 유통주식수를 총주식수로 사용
                    'par_pr': result.get('repl_pric', '500')  # 대용가를 액면가로 사용
                }
                
                logger.debug(f"종목정보 변환 완료: {stock_info_data}")
                return KiwoomStockInfo(**stock_info_data)
            else:
                logger.warning(f"종목정보 조회 실패 - return_code: {result.get('return_code')}, return_msg: {result.get('return_msg')}")
                return None
            
        except Exception as e:
            logger.error(f"주식 기본정보 조회 실패 ({symbol}): {e}")
            return None
    
    async def get_supply_demand(
        self,
        symbol: str,
        date: str,
        amt_qty_tp: str = '1',  # 1:금액, 2:수량
        trde_tp: str = '0',     # 0:순매수, 1:매수, 2:매도
        unit_tp: str = '1000'   # 1000:천주, 1:단주
    ) -> Optional[KiwoomSupplyDemand]:
        """종목별 투자자 기관별 정보 조회 (ka10059) - 실제 API 응답 구조에 맞게 수정"""
        try:
            logger.debug(f"수급데이터 조회: {symbol} {date}")
            
            data = {
                'dt': date,
                'stk_cd': symbol,
                'amt_qty_tp': amt_qty_tp,
                'trde_tp': trde_tp,
                'unit_tp': unit_tp
            }
            
            result = await self._make_request('ka10059', data)
            
            # 실제 키움 API 응답 구조: return_code 확인
            if result.get('return_code') == 0:
                # 키움 API 응답을 우리가 정의한 KiwoomSupplyDemand 구조로 변환
                supply_demand_data = {
                    'dt': date,
                    'stk_cd': symbol,
                    'frg_amt': result.get('frg_amt'),  # 외국인 금액
                    'ins_amt': result.get('ins_amt'),  # 기관 금액
                    'pns_amt': result.get('pns_amt')   # 개인 금액
                }
                return KiwoomSupplyDemand(**supply_demand_data)
            else:
                logger.warning(f"수급데이터 조회 실패 - return_code: {result.get('return_code')}, return_msg: {result.get('return_msg')}")
                return None
            
        except Exception as e:
            logger.error(f"수급데이터 조회 실패 ({symbol} {date}): {e}")
            return None
    
    async def get_multiple_stock_info(self, symbols: List[str]) -> List[KiwoomStockInfo]:
        """여러 종목 기본정보 일괄 조회"""
        logger.info(f"종목 기본정보 일괄 조회 시작: {len(symbols)}개 종목")
        
        results = []
        for symbol in symbols:
            try:
                stock_info = await self.get_stock_info(symbol)
                if stock_info:
                    results.append(stock_info)
                
                # API 호출 간격 조절
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"종목 정보 조회 실패 ({symbol}): {e}")
                continue
        
        logger.info(f"종목 기본정보 일괄 조회 완료: {len(results)}개 성공")
        return results
    
    async def get_multiple_supply_demand(
        self, 
        symbols: List[str], 
        date: str
    ) -> List[KiwoomSupplyDemand]:
        """여러 종목 수급데이터 일괄 조회"""
        logger.info(f"수급데이터 일괄 조회 시작: {len(symbols)}개 종목 ({date})")
        
        results = []
        for symbol in symbols:
            try:
                supply_demand = await self.get_supply_demand(symbol, date)
                if supply_demand:
                    results.append(supply_demand)
                
                # API 호출 간격 조절
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"수급데이터 조회 실패 ({symbol} {date}): {e}")
                continue
        
        logger.info(f"수급데이터 일괄 조회 완료: {len(results)}개 성공")
        return results
    
    async def get_all_stock_list_for_stockai(self, force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
        """
        전체 종목 리스트 조회 (ka10099)
        
        Args:
            force_refresh (bool): 강제 새로고침 여부
            
        Returns:
            Dict[str, Dict[str, str]]: {종목코드: {code: 종목코드, name: 종목명}}
        """
        # 인증 실패 시 에러 발생
        if self._auth_failed:
            raise Exception("키움 API 인증이 실패했습니다. 종목 리스트 조회 불가")
        
        # 캐시 확인 (하루에 한 번만 업데이트)
        if not force_refresh and self._stockai_stocks_cache and self._last_stockai_update:
            if datetime.now() - self._last_stockai_update < timedelta(hours=12):
                logger.info(f"[stockai] 캐시된 종목 리스트 반환: {len(self._stockai_stocks_cache)}개 종목")
                return self._stockai_stocks_cache
        
        logger.info("전체 종목 리스트 조회 시작")
        all_stocks = {}
        
        # 시장 구분별로 조회, ETF list는 따로 조회 처리.
        market_types = {
            "0": "코스피",
            "10": "코스닥", 
        }

        exclude_list = [ 'msci', 'kodex', 'kindex', 'tiger', 'arirang', 'focus', 'hanaro', 
                        'koact', 'rise', 'kiwoom', '1q', 'ace', 'sol ', 'WON ','PLUS ', 'TIMEFOLIO', '에셋플러스 ',
                        'HK ', 'BNK ', '파워 ', 'TRUSTON ', '마이티', '마이다스 ', 'VITA ', 'TRUSTON ', 'UNICORN ',
                        'KCGI ', 'DAISHIN343', 'ITF ', 'TREX ', 
                        'kbstar', 'kosef', '레버리지', '인버스', '코스피', '코스닥', '스팩',
                         'etn', 'etf', '원유', '일본' ]
        
        for mrkt_tp, market_name in market_types.items():
            try:
                logger.info(f"{market_name} 종목 조회 시작")
                market_stocks = await self._get_stock_list_by_market(mrkt_tp)
                
                for stock in market_stocks:
                    if stock.code[5] != '0' or stock.code[0] == '5'or stock.code[0] == '6' or stock.code[0] == '7':
                        continue
                    # 종목코드 4번째 자리가 숫자가 아니면 제외 (알파벳인 경우 제외)
                    if not stock.code[4].isdigit():
                        continue
                    # exclude_list의 각 단어가 종목명에 포함되어 있는지 확인 (대소문자 구분 없음)
                    if any(exclude_word.lower() in stock.name.lower() for exclude_word in exclude_list):
                        continue
                    all_stocks[stock.code] = {
                        "code": stock.code,
                        "name": stock.name,
                        "market": market_name
                    }
                
                logger.info(f"{market_name} 종목 조회 완료: {len(market_stocks)}개")
                
                # API 호출 간격 조절
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"{market_name} 종목 조회 실패: {e}")
                continue
        
        # 결과가 없으면 에러 발생
        if not all_stocks:
            error_msg = "종목 리스트 조회 결과가 없습니다. API 상태를 확인해주세요."
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 캐시 업데이트
        self._stockai_stocks_cache = all_stocks
        self._last_stockai_update = datetime.now()
        
        logger.info(f"전체 종목 리스트 조회 완료: {len(all_stocks)}개 종목")
        return all_stocks
    
    async def get_all_stock_list(self, force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
        """
        전체 종목 리스트 조회 (ka10099)
        
        Args:
            force_refresh (bool): 강제 새로고침 여부
            
        Returns:
            Dict[str, Dict[str, str]]: {종목코드: {code: 종목코드, name: 종목명}}
        """
        # 인증 실패 시 에러 발생
        if self._auth_failed:
            raise Exception("키움 API 인증이 실패했습니다. 종목 리스트 조회 불가")
        
        # 캐시 확인 (하루에 한 번만 업데이트)
        if not force_refresh and self._all_stocks_cache and self._last_stock_update:
            if datetime.now() - self._last_stock_update < timedelta(hours=12):
                logger.info(f"캐시된 종목 리스트 반환: {len(self._all_stocks_cache)}개 종목")
                return self._all_stocks_cache
        
        logger.info("전체 종목 리스트 조회 시작")
        all_stocks = {}
        
        # 시장 구분별로 조회, ETF list는 따로 조회 처리.
        market_types = {
            "0": "코스피",
            "10": "코스닥", 
            #"8": "ETF",
            # "3": "ELW",
            # "30": "K-OTC",
            # "50": "코넥스",
            # "5": "신주인수권",
            # "4": "뮤추얼펀드",
            # "6": "리츠",
            # "9": "하이일드"
        }
        
        for mrkt_tp, market_name in market_types.items():
            try:
                logger.info(f"{market_name} 종목 조회 시작")
                market_stocks = await self._get_stock_list_by_market(mrkt_tp)
                
                for stock in market_stocks:
                    all_stocks[stock.code] = {
                        "code": stock.code,
                        "name": stock.name,
                        "market": market_name
                    }
                
                logger.info(f"{market_name} 종목 조회 완료: {len(market_stocks)}개")
                
                # API 호출 간격 조절
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"{market_name} 종목 조회 실패: {e}")
                continue
        
        # 결과가 없으면 에러 발생
        if not all_stocks:
            error_msg = "종목 리스트 조회 결과가 없습니다. API 상태를 확인해주세요."
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 캐시 업데이트
        self._all_stocks_cache = all_stocks
        self._last_stock_update = datetime.now()
        
        logger.info(f"전체 종목 리스트 조회 완료: {len(all_stocks)}개 종목")
        return all_stocks
    
    async def _get_stock_list_by_market(self, mrkt_tp: str) -> List[KiwoomStockListItem]:
        """
        특정 시장의 종목 리스트 조회 (연속조회 지원) - 실제 API 응답 구조에 맞게 수정
        
        Args:
            mrkt_tp (str): 시장구분 (0:코스피,10:코스닥,3:ELW,8:ETF,30:K-OTC,50:코넥스,5:신주인수권,4:뮤추얼펀드,6:리츠,9:하이일드)
            
        Returns:
            List[KiwoomStockListItem]: 종목 리스트
        """
        all_stocks = []
        cont_yn = 'N'
        next_key = ''
        
        while True:
            try:
                await self._rate_limit()
                token = await self._ensure_token()
                
                # API 요청 데이터
                data = {"mrkt_tp": mrkt_tp}
                
                # API 호출
                result = await self._make_stock_list_request(token, data, cont_yn, next_key)
                
                # 응답 처리 - 실제 키움 API 응답 구조에 맞게 수정
                # ka10099의 경우 실제로는 'list' 필드에 종목 데이터가 들어있음
                if result.get('return_code') == 0:
                    # 실제 종목 데이터 추출
                    stock_data = None
                    if 'list' in result and isinstance(result['list'], list):
                        stock_data = result['list']
                    elif 'output' in result and isinstance(result['output'], list):
                        stock_data = result['output']
                    elif isinstance(result, list):
                        stock_data = result
                    else:
                        # 다른 구조일 경우 로깅하여 확인
                        logger.warning(f"예상하지 못한 ka10099 응답 구조: {result}")
                        break
                    
                    if not stock_data:
                        break
                    
                    # 종목 데이터 파싱
                    stocks = [KiwoomStockListItem(**item) for item in stock_data]
                    all_stocks.extend(stocks)
                    
                    logger.debug(f"시장 {mrkt_tp} 배치 조회: {len(stocks)}개 (총 {len(all_stocks)}개)")
                    
                    # 연속조회 확인
                    response_headers = result.get('response_headers', {})
                    if response_headers.get('cont-yn') != 'Y':
                        break
                    
                    # 다음 조회 준비
                    cont_yn = 'Y'
                    next_key = response_headers.get('next-key', '')
                    
                    if not next_key:
                        break
                    
                    # 연속조회 간격
                    await asyncio.sleep(0.2)
                else:
                    logger.warning(f"시장 {mrkt_tp} 종목 리스트 조회 실패 - return_code: {result.get('return_code')}")
                    break
                
            except Exception as e:
                logger.error(f"시장 {mrkt_tp} 종목 리스트 조회 중 오류: {e}")
                break
        
        return all_stocks
    
    async def _make_stock_list_request(
        self, 
        token: str, 
        data: Dict[str, Any], 
        cont_yn: str = 'N', 
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        주식 리스트 조회 API 요청 (ka10099) - 실제 API 응답 구조에 맞게 수정
        """
        url = f"{self.host}/api/dostk/stkinfo"
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka10099',
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 실제 API 응답 구조 로깅 (디버깅용)
                        logger.info(f"키움 API ka10099 응답: 총 {len(result['list'])}개 종목")
                        
                        # 응답 헤더 정보 추가 (기존 데이터 덮어쓰지 않도록 주의)
                        if 'response_headers' not in result:
                            result['response_headers'] = {
                                'next-key': response.headers.get('next-key', ''),
                                'cont-yn': response.headers.get('cont-yn', 'N'),
                                'api-id': response.headers.get('api-id', 'ka10099')
                            }
                        
                        return result
                    else:
                        error_text = await response.text()
                        error_msg = f"종목 리스트 API 호출 실패: {response.status} - {error_text}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                        
        except Exception as e:
            error_msg = f"종목 리스트 API 요청 중 오류: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
    async def get_stock_list_for_stockai(self) -> List[Dict[str, str]]:
        """
        프론트엔드용 종목 리스트 반환 (code, name만)
        
        Returns:
            List[Dict[str, str]]: [{"code": "005930", "name": "삼성전자"}, ...]
        """
        try:
            all_stocks = await self.get_all_stock_list_for_stockai()
            
            # code, name만 추출
            result = []
            for stock_info in all_stocks.values():
                result.append(stock_info)
            
            logger.info(f"stock ai용 종목 리스트 반환: {len(result)}개")
            return result
            
        except Exception as e:
            error_msg = f"stock ai용 종목 리스트 조회 실패: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
    async def get_stock_list_for_frontend(self) -> List[Dict[str, str]]:
        """
        프론트엔드용 종목 리스트 반환 (code, name만)
        
        Returns:
            List[Dict[str, str]]: [{"code": "005930", "name": "삼성전자"}, ...]
        """
        try:
            all_stocks = await self.get_all_stock_list()
            
            # code, name만 추출
            result = []
            for stock_info in all_stocks.values():
                result.append(stock_info)
            
            logger.info(f"프론트엔드용 종목 리스트 반환: {len(result)}개")
            return result
            
        except Exception as e:
            error_msg = f"프론트엔드용 종목 리스트 조회 실패: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
    
    
    def get_stats(self) -> Dict[str, Any]:
        """API 호출 통계"""
        return {
            "total_requests": self.request_count,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "is_token_valid": self.access_token is not None,
            "cached_stocks_count": len(self._all_stocks_cache),
            "last_stock_update": self._last_stock_update.isoformat() if self._last_stock_update else None,
            "cached_stockai_stocks_count": len(self._stockai_stocks_cache),
            "last_stockai_update": self._last_stockai_update.isoformat() if self._last_stockai_update else None,
        }
    
    async def close(self) -> None:
        """클라이언트 정리"""
        logger.info("키움 API 클라이언트 정리 중...")
        # 필요한 정리 작업 수행
        logger.info("키움 API 클라이언트 정리 완료") 