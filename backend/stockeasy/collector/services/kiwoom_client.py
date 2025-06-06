"""
키움증권 REST API 클라이언트

새로운 통합 API 사용법:

# 1. 기본 API 호출
result = await client.call_api(
    api_id='ka10001',
    endpoint='/api/dostk/stkinfo',
    data={'stk_cd': '005930'}
)

# 2. 카테고리별 편의 함수 사용
result = await client.call_stock_info_api('ka10001', {'stk_cd': '005930'})
result = await client.call_account_api('ka10072', account_data)
result = await client.call_market_condition_api('ka10063', market_data)

# 3. 특정 TR 전용 함수 사용
result = await client.get_daily_realized_profit_loss(account_data)
result = await client.get_investor_trading_by_market(market_data)

# 4. 연속조회 예시
result = await client.call_api(
    api_id='ka10099',
    endpoint='/api/dostk/stkinfo',
    data={'mrkt_tp': '0'},
    cont_yn='Y',
    next_key='received_next_key'
)
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


class KiwoomChartData(BaseModel):
    """키움 일봉차트 데이터 (ka10081)"""
    date: str                          # 날짜
    open: Optional[str] = None         # 시가
    high: Optional[str] = None         # 고가  
    low: Optional[str] = None          # 저가
    close: Optional[str] = None        # 종가
    volume: Optional[str] = None       # 거래량
    trading_value: Optional[str] = None # 거래대금
    change_amount: Optional[str] = None # 전일대비
    change_rate: Optional[str] = None   # 등락률
    previous_close: Optional[str] = None # 전일종가


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
        """API 호출 제한 관리 - 키움 TR 제약: 초당 4.8회 (0.208초 간격)"""
        async with self.semaphore:
            current_time = asyncio.get_event_loop().time()
            time_diff = current_time - self.last_request_time
            
            # 키움 API 제약: 초당 4.8회 = 0.208초 간격
            MIN_INTERVAL = 0.208  # 초당 4.8회
            
            if time_diff < MIN_INTERVAL:
                sleep_time = MIN_INTERVAL - time_diff
                logger.debug(f"API 호출 제한 대기: {sleep_time:.3f}초")
                await asyncio.sleep(sleep_time)
            
            self.last_request_time = asyncio.get_event_loop().time()
            self.request_count += 1
    
    async def _make_kiwoom_api_request(
        self,
        api_id: str,
        endpoint: str,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        키움 API 통합 요청 처리 함수
        
        Args:
            api_id (str): TR명 (예: ka10001, ka10059, ka10072, ka10063, ka10099)
            endpoint (str): API 엔드포인트 (예: /api/dostk/stkinfo, /api/dostk/acnt, /api/dostk/mrkcond)
            data (Dict[str, Any]): 요청 데이터
            cont_yn (str): 연속조회여부 ('N' 또는 'Y')
            next_key (str): 연속조회키
            
        Returns:
            Dict[str, Any]: API 응답 데이터
        """
        # 인증 실패 시 에러 발생
        if self._auth_failed:
            raise Exception(f"키움 API 인증이 실패했습니다. {api_id} 호출 불가")
        
        await self._rate_limit()
        token = await self._ensure_token()
        
        url = f"{self.host}{endpoint}"
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
                        logger.debug(f"키움 API 응답 ({api_id}): 상태코드={response.status}")
                        
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
            
            result = await self._make_kiwoom_api_request('ka10001', '/api/dostk/stkinfo', data)
            
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
            logger.info(f"수급데이터 조회: {symbol} {date}")
            
            data = {
                'dt': date,
                'stk_cd': symbol,
                'amt_qty_tp': amt_qty_tp,
                'trde_tp': trde_tp,
                'unit_tp': unit_tp
            }
            
            result = await self._make_kiwoom_api_request('ka10059', '/api/dostk/stkinfo', data)
            
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
                    
                    # API 호출 간격은 _rate_limit()에서 자동 관리됨 (0.208초 간격)
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
        주식 리스트 조회 API 요청 (ka10099) - 통합 함수 사용으로 간소화
        """
        return await self._make_kiwoom_api_request('ka10099', '/api/dostk/stkinfo', data, cont_yn, next_key)
        
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

    async def call_api(
        self,
        api_id: str,
        endpoint: str,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        키움 API 직접 호출 함수 (외부에서 사용 가능)
        
        Args:
            api_id (str): TR명 (예: ka10001, ka10059, ka10072, ka10063, ka10099)
            endpoint (str): API 엔드포인트 (예: /api/dostk/stkinfo, /api/dostk/acnt, /api/dostk/mrkcond)
            data (Dict[str, Any]): 요청 데이터
            cont_yn (str): 연속조회여부 ('N' 또는 'Y')
            next_key (str): 연속조회키
            
        Returns:
            Dict[str, Any]: API 응답 데이터
        """
        logger.info(f"키움 API 호출: {api_id} -> {endpoint}")
        return await self._make_kiwoom_api_request(api_id, endpoint, data, cont_yn, next_key)
    
    async def call_stock_info_api(
        self,
        api_id: str,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        주식정보 관련 API 호출 (/api/dostk/stkinfo)
        
        Args:
            api_id (str): TR명 (예: ka10001, ka10059, ka10099 등)
            data (Dict[str, Any]): 요청 데이터
            cont_yn (str): 연속조회여부
            next_key (str): 연속조회키
            
        Returns:
            Dict[str, Any]: API 응답 데이터
        """
        return await self._make_kiwoom_api_request(api_id, '/api/dostk/stkinfo', data, cont_yn, next_key)
    
    async def call_account_api(
        self,
        api_id: str,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        계좌 관련 API 호출 (/api/dostk/acnt)
        
        Args:
            api_id (str): TR명 (예: ka10072 등)
            data (Dict[str, Any]): 요청 데이터
            cont_yn (str): 연속조회여부
            next_key (str): 연속조회키
            
        Returns:
            Dict[str, Any]: API 응답 데이터
        """
        return await self._make_kiwoom_api_request(api_id, '/api/dostk/acnt', data, cont_yn, next_key)
    
    async def call_market_condition_api(
        self,
        api_id: str,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        시장상황 관련 API 호출 (/api/dostk/mrkcond)
        
        Args:
            api_id (str): TR명 (예: ka10063 등)
            data (Dict[str, Any]): 요청 데이터
            cont_yn (str): 연속조회여부
            next_key (str): 연속조회키
            
        Returns:
            Dict[str, Any]: API 응답 데이터
        """
        return await self._make_kiwoom_api_request(api_id, '/api/dostk/mrkcond', data, cont_yn, next_key)
    
    # 특정 TR 전용 편의 함수들
    async def get_daily_realized_profit_loss(
        self,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        일자별종목별실현손익 조회 (ka10072)
        
        Args:
            data: 요청 데이터 (계좌정보, 일자 등 포함)
            cont_yn: 연속조회여부
            next_key: 연속조회키
            
        Returns:
            Dict[str, Any]: 실현손익 데이터
        """
        logger.info(f"일자별종목별실현손익 조회: {data}")
        return await self.call_account_api('ka10072', data, cont_yn, next_key)
    
    async def get_investor_trading_by_market(
        self,
        data: Dict[str, Any],
        cont_yn: str = 'N',
        next_key: str = ''
    ) -> Dict[str, Any]:
        """
        장중투자자별매매 조회 (ka10063)
        
        Args:
            data: 요청 데이터 (날짜, 시장구분 등 포함)
            cont_yn: 연속조회여부
            next_key: 연속조회키
            
        Returns:
            Dict[str, Any]: 투자자별 매매 데이터
        """
        logger.info(f"장중투자자별매매 조회: {data}")
        return await self.call_market_condition_api('ka10063', data, cont_yn, next_key)

    async def get_daily_chart_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjusted_price: str = '1'  # 1:수정주가, 0:원주가
    ) -> List[KiwoomChartData]:
        """
        일봉차트 데이터 조회 (ka10081) - 연속조회 지원
        
        Args:
            symbol (str): 종목코드
            start_date (str): 시작일자 (YYYYMMDD) - 실제로는 base_dt로 사용됨
            end_date (str): 종료일자 (YYYYMMDD) - 키움 API에서는 사용하지 않음
            adjusted_price (str): 수정주가구분 (1:수정주가, 0:원주가)
            
        Returns:
            List[KiwoomChartData]: 차트 데이터 리스트 (최신순)
        """
        try:
            # 기준일자는 end_date(최근일자)를 사용
            base_date = end_date
            logger.info(f"일봉차트 데이터 조회: {symbol} (기준일자: {base_date})")
            
            all_chart_data = []
            cont_yn = 'N'
            next_key = ''
            
            while True:
                # 키움 API ka10081 요청 형식에 맞게 수정
                data = {
                    'stk_cd': symbol,
                    'base_dt': base_date,
                    'upd_stkpc_tp': adjusted_price
                }
                
                result = await self._make_kiwoom_api_request('ka10081', '/api/dostk/chart', data, cont_yn, next_key)
                
                if result.get('return_code') == 0:
                    # 차트 데이터 추출 - ka10081 응답 구조에 맞게 수정
                    chart_data = None
                    if 'stk_dt_pole_chart_qry' in result and isinstance(result['stk_dt_pole_chart_qry'], list):
                        chart_data = result['stk_dt_pole_chart_qry']
                    elif 'output' in result and isinstance(result['output'], list):
                        chart_data = result['output']
                    elif 'list' in result and isinstance(result['list'], list):
                        chart_data = result['list']
                    elif isinstance(result, list):
                        chart_data = result
                    
                    if not chart_data:
                        break
                    
                    # 데이터 변환 및 기간 필터링 - ka10081 실제 필드명 사용
                    for item in chart_data:
                        try:
                            item_date = item.get('dt', '')  # 실제 필드명: dt
                            
                            # start_date 이전 데이터는 제외 (기간 필터링)
                            if item_date and item_date < start_date:
                                logger.debug(f"기간 필터링: {item_date} < {start_date}, 수집 종료")
                                return all_chart_data  # 더 이상 진행하지 않고 종료
                            
                            # 전일대비 및 등락률 계산
                            current_price = item.get('cur_prc', '0')  # 현재가
                            prev_close = item.get('pred_close_pric', '0')  # 전일종가
                            
                            change_amount = '0'
                            change_rate = '0'
                            if current_price and prev_close and prev_close != '0':
                                try:
                                    cur_val = float(current_price)
                                    prev_val = float(prev_close)
                                    change_amount = str(int(cur_val - prev_val))
                                    if prev_val != 0:
                                        change_rate = str(round((cur_val - prev_val) / prev_val * 100, 2))
                                except (ValueError, ZeroDivisionError):
                                    pass
                            
                            chart_item = KiwoomChartData(
                                date=item_date,
                                open=item.get('open_pric', '0'),      # 시가
                                high=item.get('high_pric', '0'),      # 고가
                                low=item.get('low_pric', '0'),        # 저가
                                close=current_price,                   # 종가 (현재가)
                                volume=item.get('trde_qty', '0'),     # 거래량
                                trading_value=item.get('trde_prica', '0'),  # 거래대금
                                change_amount=change_amount,           # 전일대비 (계산)
                                change_rate=change_rate,               # 등락률 (계산)
                                previous_close=prev_close              # 전일종가
                            )
                            all_chart_data.append(chart_item)
                        except Exception as e:
                            logger.warning(f"차트 데이터 변환 실패: {item}, 오류: {e}")
                            continue
                    
                    logger.debug(f"차트 데이터 배치 조회: {len(chart_data)}개 (총 {len(all_chart_data)}개)")
                    
                    # 연속조회 확인
                    response_headers = result.get('response_headers', {})
                    if response_headers.get('cont-yn') != 'Y':
                        break
                    
                    # 다음 조회 준비
                    cont_yn = 'Y'
                    next_key = response_headers.get('next-key', '')
                    
                    if not next_key:
                        break
                    
                    # API 호출 간격은 _rate_limit()에서 자동 관리됨 (0.208초 간격)
                else:
                    logger.warning(f"차트 데이터 조회 실패 - return_code: {result.get('return_code')}, return_msg: {result.get('return_msg')}")
                    break
            
            logger.info(f"일봉차트 데이터 조회 완료: {symbol} ({start_date} ~ {base_date}) - {len(all_chart_data)}개")
            return all_chart_data
            
        except Exception as e:
            logger.error(f"일봉차트 데이터 조회 실패 ({symbol}): {e}")
            return []

    async def get_supply_demand_detailed(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        amt_qty_tp: str = '1',  # 1:금액, 2:수량
        trde_tp: str = '0',     # 0:순매수, 1:매수, 2:매도
        unit_tp: str = '1000'   # 1000:천주, 1:단주
    ) -> List[Dict[str, Any]]:
        """
        수급 데이터 상세 조회 (ka10059) - 연속조회 지원
        
        Args:
            symbol (str): 종목코드
            start_date (str): 시작일자 (YYYYMMDD)
            end_date (str): 종료일자 (YYYYMMDD)
            amt_qty_tp (str): 금액수량구분 (1:금액, 2:수량)
            trde_tp (str): 매매구분 (0:순매수, 1:매수, 2:매도)
            unit_tp (str): 단위구분 (1000:천주, 1:단주)
            
        Returns:
            List[Dict[str, Any]]: 수급 데이터 리스트 (최신순)
        """
        try:
            # 기준일자는 end_date(최근일자)를 사용
            base_date = end_date
            logger.info(f"수급 데이터 상세 조회: {symbol} (기준일자: {base_date}, 목표일자: {start_date})")
            
            all_supply_data = []
            cont_yn = 'N'
            next_key = ''
            
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y%m%d')
            
            while True:
                try:
                    data = {
                        'dt': base_date,
                        'stk_cd': symbol,
                        'amt_qty_tp': amt_qty_tp,
                        'trde_tp': trde_tp,
                        'unit_tp': unit_tp
                    }
                    
                    result = await self._make_kiwoom_api_request('ka10059', '/api/dostk/stkinfo', data, cont_yn, next_key)
                    
                    if result.get('return_code') == 0:
                        # 배치 데이터 처리 (stk_invsr_orgn 배열)
                        stk_invsr_orgn = result.get('stk_invsr_orgn', [])
                        if not stk_invsr_orgn:
                            logger.warning(f"수급 데이터 없음: {symbol} {base_date}")
                            break
                        
                        batch_data = []
                        last_date = None
                        
                        for item in stk_invsr_orgn:
                            try:
                                item_date_str = item.get('dt', '')
                                if not item_date_str:
                                    continue
                                
                                item_date = datetime.strptime(item_date_str, '%Y%m%d')
                                last_date = item_date_str
                                
                                # 키움 API 필드 → 우리 스키마 필드 매핑
                                # 가격 정보에서 부호 제거 ("+61300" → "61300")
                                cur_prc = item.get('cur_prc', '0')
                                if cur_prc.startswith(('+', '-')):
                                    current_price = cur_prc[1:]  # 부호 제거
                                else:
                                    current_price = cur_prc
                                
                                pred_pre = item.get('pred_pre', '0')
                                if pred_pre.startswith(('+', '-')):
                                    price_change = pred_pre[1:]  # 부호 제거
                                    price_change_sign = '+' if pred_pre.startswith('+') else '-'
                                else:
                                    price_change = pred_pre
                                    price_change_sign = '0'
                                
                                flu_rt = item.get('flu_rt', '0')
                                if flu_rt.startswith(('+', '-')):
                                    price_change_percent = flu_rt[1:]  # 부호 제거
                                else:
                                    price_change_percent = flu_rt
                                
                                # 수급 데이터 변환
                                supply_data = {
                                    'date': item_date_str,
                                    'symbol': symbol,
                                    'current_price': current_price,
                                    'price_change_sign': price_change_sign,
                                    'price_change': price_change,
                                    'price_change_percent': price_change_percent,
                                    'accumulated_volume': item.get('acc_trde_qty'),
                                    'accumulated_value': item.get('acc_trde_prica'),
                                    'individual_investor': item.get('ind_invsr'),
                                    'foreign_investor': item.get('frgnr_invsr'),
                                    'institution_total': item.get('orgn'),
                                    'financial_investment': item.get('fnnc_invt'),
                                    'insurance': item.get('insrnc'),
                                    'investment_trust': item.get('invtrt'),
                                    'other_financial': item.get('etc_fnnc'),
                                    'bank': item.get('bank'),
                                    'pension_fund': item.get('penfnd_etc'),
                                    'private_fund': item.get('samo_fund'),
                                    'government': item.get('natn'),
                                    'other_corporation': item.get('etc_corp'),
                                    'domestic_foreign': item.get('natfor')
                                }
                                batch_data.append(supply_data)
                                
                                # start_date에 도달했으면 중단
                                if item_date <= start_date_obj:
                                    break
                                    
                            except Exception as e:
                                logger.warning(f"수급 데이터 변환 실패: {item}, 오류: {e}")
                                continue
                        
                        all_supply_data.extend(batch_data)
                        logger.debug(f"수급 데이터 배치 조회: {len(batch_data)}개 (총 {len(all_supply_data)}개)")
                        
                        # start_date에 도달했으면 중단
                        if last_date:
                            last_date_obj = datetime.strptime(last_date, '%Y%m%d')
                            if last_date_obj <= start_date_obj:
                                logger.info(f"목표 시작일자({start_date}) 도달: 마지막 조회일자 {last_date}")
                                break
                        
                        # 연속조회 확인
                        response_headers = result.get('response_headers', {})
                        if response_headers.get('cont-yn') != 'Y':
                            break
                        
                        # 다음 조회 준비
                        cont_yn = 'Y'
                        next_key = response_headers.get('next-key', '')
                        
                        if not next_key:
                            break
                        
                        # API 호출 간격은 _rate_limit()에서 자동 관리됨 (0.208초 간격)
                    else:
                        logger.warning(f"수급 데이터 조회 실패 - return_code: {result.get('return_code')}, return_msg: {result.get('return_msg')}")
                        break
                        
                except Exception as e:
                    logger.error(f"수급 데이터 조회 오류 ({symbol} {base_date}): {e}")
                    break
            
            logger.info(f"수급 데이터 상세 조회 완료: {symbol} ({start_date} ~ {end_date}) - {len(all_supply_data)}개")
            return all_supply_data
            
        except Exception as e:
            logger.error(f"수급 데이터 상세 조회 실패 ({symbol}): {e}")
            return []

    async def get_multiple_chart_data(
        self, 
        symbols: List[str], 
        start_date: str, 
        end_date: str,
        max_concurrent: int = 3  # 사용하지 않음 (하위 호환성을 위해 유지)
    ) -> Dict[str, List[KiwoomChartData]]:
        """
        여러 종목 차트 데이터 순차 조회 (키움 API 제약: 초당 4.8회)
        
        Args:
            symbols (List[str]): 종목코드 리스트
            start_date (str): 시작일자 (YYYYMMDD)
            end_date (str): 종료일자 (YYYYMMDD)
            max_concurrent (int): 사용하지 않음 (하위 호환성)
            
        Returns:
            Dict[str, List[KiwoomChartData]]: {종목코드: 차트데이터리스트}
        """
        logger.info(f"여러 종목 차트 데이터 순차 조회: {len(symbols)}개 종목")
        
        chart_data_dict = {}
        success_count = 0
        
        # 키움 API 제약: 초당 4.8회 = 0.208초 간격
        API_CALL_INTERVAL = 0.208  # 초당 4.8회
        
        for i, symbol in enumerate(symbols):
            try:
                logger.debug(f"차트 데이터 조회 진행: {i+1}/{len(symbols)} - {symbol}")
                
                chart_data = await self.get_daily_chart_data(symbol, start_date, end_date)
                chart_data_dict[symbol] = chart_data
                
                if chart_data:
                    success_count += 1
                    logger.debug(f"차트 데이터 조회 성공: {symbol} - {len(chart_data)}건")
                else:
                    logger.warning(f"차트 데이터 조회 결과 없음: {symbol}")
                
                # API 호출 제한 준수 (마지막 호출 제외)
                if i < len(symbols) - 1:
                    await asyncio.sleep(API_CALL_INTERVAL)
                
            except Exception as e:
                logger.error(f"종목 차트 데이터 조회 실패 ({symbol}): {e}")
                chart_data_dict[symbol] = []
                
                # 에러 발생 시에도 대기 (API 제한 준수)
                if i < len(symbols) - 1:
                    await asyncio.sleep(API_CALL_INTERVAL)
        
        logger.info(f"여러 종목 차트 데이터 순차 조회 완료: {success_count}/{len(symbols)}개 성공")
        return chart_data_dict

    async def get_multiple_supply_demand_data(
        self, 
        symbols: List[str], 
        start_date: str, 
        end_date: str,
        max_concurrent: int = 2  # 사용하지 않음 (하위 호환성을 위해 유지)
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        여러 종목 수급 데이터 순차 조회 (키움 API 제약: 초당 4.8회)
        
        Args:
            symbols (List[str]): 종목코드 리스트
            start_date (str): 시작일자 (YYYYMMDD)
            end_date (str): 종료일자 (YYYYMMDD)
            max_concurrent (int): 사용하지 않음 (하위 호환성)
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: {종목코드: 수급데이터리스트}
        """
        logger.info(f"여러 종목 수급 데이터 순차 조회: {len(symbols)}개 종목")
        
        supply_data_dict = {}
        success_count = 0
        
        # 키움 API 제약: 초당 4.8회 = 0.208초 간격
        API_CALL_INTERVAL = 0.208  # 초당 4.8회
        
        for i, symbol in enumerate(symbols):
            try:
                logger.debug(f"수급 데이터 조회 진행: {i+1}/{len(symbols)} - {symbol}")
                
                supply_data = await self.get_supply_demand_detailed(symbol, start_date, end_date)
                supply_data_dict[symbol] = supply_data
                
                if supply_data:
                    success_count += 1
                    logger.info(f"수급 데이터 조회 성공: {symbol} - {len(supply_data)}건")
                else:
                    logger.warning(f"수급 데이터 조회 결과 없음: {symbol}")
                
                # API 호출 제한 준수 (마지막 호출 제외)
                if i < len(symbols) - 1:
                    await asyncio.sleep(API_CALL_INTERVAL)
                
            except Exception as e:
                logger.error(f"종목 수급 데이터 조회 실패 ({symbol}): {e}")
                supply_data_dict[symbol] = []
                
                # 에러 발생 시에도 대기 (API 제한 준수)
                if i < len(symbols) - 1:
                    await asyncio.sleep(API_CALL_INTERVAL)
        
        logger.info(f"여러 종목 수급 데이터 순차 조회 완료: {success_count}/{len(symbols)}개 성공")
        return supply_data_dict 