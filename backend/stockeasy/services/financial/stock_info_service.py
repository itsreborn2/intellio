"""
종목 정보 서비스 클래스

이 모듈은 종목 코드 및 이름을 관리하고 조회하기 위한 서비스를 제공합니다.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

import pandas as pd
from loguru import logger
from common.core.config import settings

from stockeasy.services.google_sheet_service import GoogleSheetService


class StockInfoService:
    """종목 정보 서비스 클래스"""
    _instance = None
    _stock_info_cache = None  # 메모리 캐시
    _last_update_date = None  # 마지막 업데이트 날짜
    _update_task = None  # 자동 업데이트 태스크
    _initialized = None  # 초기화 완료 이벤트
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = asyncio.Event()  # 초기화 이벤트 생성
            # 기본 빈 데이터 구조로 초기화 (최소한의 동작 보장)
            cls._instance._stock_info_cache = {"by_code": {}, "by_name": {}, "sector": {}}
            # 백그라운드에서 초기화 진행
            asyncio.create_task(cls._instance._initialize())
            # 바로 사용 가능하도록 초기화 완료 이벤트 설정
            cls._instance._initialized.set()
            print("기본 구조로 초기화 완료, 백그라운드에서 전체 데이터 로딩 중...")
        return cls._instance
    
    async def _initialize(self) -> None:
        """
        주식 정보를 초기화하고 캐싱합니다.
        """
        logger.info("주식 정보 서비스 초기화 시작")
        print("주식 정보 서비스 초기화 시작")
        
        # 종목 정보 캐시 경로
        self.cache_dir = Path(settings.STOCKEASY_LOCAL_CACHE_DIR)
        self.stock_info_path = self.cache_dir / "stock_info.json"
        
        # 캐시 디렉토리 생성
        os.makedirs(self.cache_dir, exist_ok=True)

        try:
            # 캐시 파일이 있는지 확인
            if os.path.exists(self.stock_info_path):
                # 캐시 파일 읽기
                with open(self.stock_info_path, 'r', encoding='utf-8') as f:
                    self._stock_info_cache = json.load(f)
                    logger.info("주식 정보 캐시 파일 로드 완료")
            else:
                # 캐시 파일이 없으면 KRX에서 데이터 가져오기
                if self._stock_info_cache is None:
                    logger.info("캐시 파일이 없어 KRX에서 초기 데이터를 가져옵니다")
                    self._stock_info_cache = await self._fetch_stock_info_from_krx()
                    
                    # 구글 시트에서 섹터 정보 가져오기
                    self._stock_sector_dict = self.make_sector_dict_from_google_sheet()
                    
                    # 섹터 정보 업데이트 - 종목코드가 일치하는 경우에만
                    if self._stock_sector_dict:
                        # _stock_info_cache에 sector 키가 없으면 추가
                        if "sector" not in self._stock_info_cache:
                            self._stock_info_cache["sector"] = {}
                        
                        # 종목코드가 일치하는 경우 섹터 정보 추가
                        updated_count = 0
                        for code, sector_info in self._stock_sector_dict.items():
                            # _stock_info_cache["by_code"]에 해당 종목코드가 있는 경우에만 추가
                            if code in self._stock_info_cache["by_code"]:
                                # 1. stock_info_cache["sector"]에 추가
                                self._stock_info_cache["sector"][code] = sector_info
                                
                                # 2. 개별 종목 정보에도 섹터 추가
                                self._stock_info_cache["by_code"][code]["sector"] = sector_info
                                updated_count += 1
                        
                        logger.info(f"구글 시트에서 가져온 섹터 정보 {updated_count}개 업데이트 완료")
                    
                    # 파일 캐시 저장
                    with open(self.stock_info_path, 'w', encoding='utf-8') as f:
                        json.dump(self._stock_info_cache, f, ensure_ascii=False, indent=2)
                        logger.info("초기 주식 정보 캐시 파일 생성 완료")
        except Exception as e:
            logger.error(f"주식 정보 초기화 실패: {str(e)}")
            self._stock_info_cache = {"by_code": {}, "by_name": {}, "sector": {}}
        
        # 자동 업데이트 태스크 시작
        self._update_task = asyncio.create_task(self._start_auto_update())
        logger.info("주식 정보 서비스 초기화 완료")
        try:
            stocks = await self.search_stocks("삼성전", limit=5)
            logger.info(f"샘플 종목 검색 결과: {len(stocks)}개")
            print(f"샘플 종목 검색 결과: {len(stocks)}개")
            for i, stock in enumerate(stocks):
                sector_info = stock.get('sector', '정보 없음')
                logger.info(f"[{i+1}] 종목명: {stock['name']}, 종목코드: {stock['code']}, 업종: {sector_info}")

            logger.info("섹터 조회 시작")
            sector = await self.get_sector_by_code("278470")
            logger.info(f"섹터 조회 결과 278470 : {sector}")
        except Exception as e:
            logger.error(f"샘플 종목 및 섹터 조회 중 오류 발생: {str(e)}")
        
        # 초기화 완료 이벤트 설정
        self._initialized.set()
        logger.info("주식 정보 서비스 초기화 이벤트 설정 완료")
    
    async def wait_for_initialization(self) -> None:
        """
        초기화가 완료될 때까지 기다립니다.
        """
        await self._initialized.wait()
    async def force_update(self):
        """강제 업데이트 태스크를 시작합니다."""
        logger.info("주식 정보 강제 업데이트 태스크 시작")
        print("주식 정보 업데이트 시작")
        stock_info = await self._fetch_stock_info_from_krx()
        
    async def _start_auto_update(self):
        """자동 업데이트 태스크를 시작합니다."""
        logger.info("주식 정보 자동 업데이트 태스크 시작")
        print("주식 정보 자동 업데이트 태스크 시작")
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
                print(f"다음 주식 정보 업데이트 예정 시각: {target_time}")
                await asyncio.sleep(wait_seconds)
                
                # 7:30이 되면 데이터 갱신
                logger.info("예정된 시각에 주식 정보 업데이트 시작")

                logger.info("KRX 종목 정보 업데이트 시작")
                await self.update_all_stock_from_krx()
                logger.info("KRX 종목 정보 업데이트 완료")
                
                stock_info = await self._fetch_stock_info_from_krx()
                
                # 이전 _stock_info_cache에서 sector 정보 보존
                if self._stock_info_cache and "sector" in self._stock_info_cache:
                    if "sector" not in stock_info:
                        stock_info["sector"] = {}
                    stock_info["sector"] = self._stock_info_cache["sector"]
                
                # 구글 시트에서 최신 섹터 정보 가져와서 업데이트
                logger.info("구글 시트에서 최신 섹터 정보 가져오기")
                sector_dict = self.make_sector_dict_from_google_sheet()
                
                # 섹터 정보 업데이트
                if sector_dict:
                    # sector 키가 없으면 추가
                    if "sector" not in stock_info:
                        stock_info["sector"] = {}
                    
                    # 종목코드가 일치하는 경우에만 섹터 정보 추가/업데이트
                    updated_count = 0
                    for code, sector_info in sector_dict.items():
                        if code in stock_info["by_code"]:
                            # 1. sector 섹션에 추가
                            stock_info["sector"][code] = sector_info
                            
                            # 2. 개별 종목 정보에도 섹터 추가
                            stock_info["by_code"][code]["sector"] = sector_info
                            updated_count += 1
                    
                    logger.info(f"구글 시트에서 가져온 섹터 정보 {updated_count}개 업데이트 완료")
                
                # 메모리 캐시 업데이트
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
        # 초기화 완료 이벤트는 이미 설정되어 있으므로 바로 반환
        # await self._initialized.wait()
        return self._stock_info_cache or {"by_code": {}, "by_name": {}}
        
    async def _fetch_stock_info_from_krx(self) -> Dict[str, Any]:
        """
        KRX에서 종목 정보를 조회합니다.
        
        Returns:
            종목 정보 딕셔너리
        """
        try:
            # KRX에서 종목 정보 조회
            print("KRX에서 종목 정보 조회 시작")
            krx_data = await self.read_krx_code()
            print("KRX에서 종목 정보 조회 완료")
            
            # 데이터 변환
            by_code = {}
            by_name = {}
            
            for _, row in krx_data.iterrows():
                stock_info = {
                    "code": row["code"],
                    "name": row["name"],
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
        
    def get_stocks_by_sector_from_google_sheet(sector_dict, target_sector):
        """
        특정 섹터에 속하는 모든 종목코드 리스트 반환
        
        Args:
            sector_dict: 종목코드:섹터 딕셔너리
            target_sector: 찾을 섹터명
            
        Returns:
            List[str]: 해당 섹터에 속하는 종목코드 리스트
        """
        result = []
        
        for code, sectors in sector_dict.items():
            if isinstance(sectors, list):
                # 섹터가 리스트인 경우 (콤마로 구분된 여러 섹터)
                if target_sector in sectors:
                    result.append(code)
            else:
                # 섹터가 단일 문자열인 경우
                if sectors == target_sector:
                    result.append(code)
        
        return result
    
    def make_sector_dict_from_google_sheet(self) -> Dict[str, Any]:
        """
        구글 시트에서 섹터 정보를 가져와 딕셔너리로 반환합니다.
        종목코드를 키로 하고 섹터 정보를 값으로 합니다.
        
        Returns:
            Dict[str, Any]: 종목코드:섹터 딕셔너리
        """
        try:
            print("구글 시트에서 섹터 정보 가져오기 시작")
            logger.info("구글 시트에서 섹터 정보 가져오기 시작")
            
            from stockeasy.services.google_sheet_service import GoogleSheetService
            
            # 구글 시트 서비스 초기화
            sheet_service = GoogleSheetService(credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS)
            
            # 최대 60초 타임아웃 설정 (기존 요청을 래핑)
            import concurrent.futures
            import asyncio
            
            executor = concurrent.futures.ThreadPoolExecutor()
            loop = asyncio.get_event_loop()
            
            # 처리 함수 정의
            def get_sector_from_sheet():
                # 스프레드시트 URL로 열기
                sheet_url = "https://docs.google.com/spreadsheets/d/1AgbEpblhoqSBTmryDjSSraqc5lRdgWKNwBUA4VYk2P4/edit"
                # 섹터 딕셔너리 가져오기
                return sheet_service.get_sector_dict(url=sheet_url, worksheet_name="섹터")
            
            # 타임아웃과 함께 실행
            try:
                print("구글 시트 요청 시작 (60초 타임아웃)")
                logger.info("구글 시트 요청 시작 (60초 타임아웃)")
                
                # ThreadPoolExecutor로 실행하고 타임아웃 설정
                future = executor.submit(get_sector_from_sheet)
                sector_dict = {}
                
                # 최대 60초 기다림
                try:
                    sector_dict = future.result(timeout=60)
                except concurrent.futures.TimeoutError:
                    print("구글 시트 요청 타임아웃 (60초 초과)")
                    logger.warning("구글 시트 요청 타임아웃 (60초 초과)")
                    return {}  # 타임아웃 시 빈 딕셔너리 반환
                finally:
                    executor.shutdown(wait=False)
                
                if sector_dict:
                    print(f"구글 시트에서 {len(sector_dict)}개 종목의 섹터 정보를 가져왔습니다.")
                    logger.info(f"구글 시트에서 {len(sector_dict)}개 종목의 섹터 정보를 가져왔습니다.")
                else:
                    print("구글 시트에서 섹터 정보를 가져오지 못했습니다.")
                    logger.warning("구글 시트에서 섹터 정보를 가져오지 못했습니다.")
                
                return sector_dict
            except Exception as inner_e:
                print(f"구글 시트 요청 처리 중 오류: {str(inner_e)}")
                logger.error(f"구글 시트 요청 처리 중 오류: {str(inner_e)}")
                return {}
            
        except ImportError as e:
            print(f"GoogleSheetService 가져오기 실패 (gspread 라이브러리 설치 필요): {str(e)}")
            logger.error(f"GoogleSheetService 가져오기 실패 (gspread 라이브러리 설치 필요): {str(e)}")
            return {}
        except Exception as e:
            print(f"구글 시트에서 섹터 정보 가져오기 실패: {str(e)}")
            logger.error(f"구글 시트에서 섹터 정보 가져오기 실패: {str(e)}")
            return {}

    async def get_sector_by_code(self, stock_code: str) -> Optional[Any]:
        """
        종목 코드로 섹터 정보를 조회합니다.
        
        Args:
            stock_code: 종목 코드
            
        Returns:
            섹터 정보 (문자열 또는 리스트) 또는 None
        """
        stock_info = await self._load_stock_info()
        if not stock_info or "sector" not in stock_info:
            return None
        
        # sector 정보에서 조회
        sector_map = stock_info.get("sector", {})
        if stock_code in sector_map:
            return sector_map.get(stock_code)
        
        # by_code 내의 stock_info에서 sector 필드 조회
        code_map = stock_info.get("by_code", {})
        if stock_code in code_map and "sector" in code_map[stock_code]:
            return code_map[stock_code]["sector"]
            
        return None
        
    async def get_all_stock_codes(self) -> List[str]:
        """
        모든 종목코드 리스트를 반환합니다.
        
        Returns:
            List[str]: 오름차순으로 정렬된 모든 종목코드 리스트
        """
        stock_info = await self._load_stock_info()
        if not stock_info:
            return []
            
        # by_code 키에서 모든 종목코드(키) 추출 후 오름차순 정렬
        return sorted(list(stock_info.get("by_code", {}).keys()))
    
    async def update_all_stock_from_krx(self):
        """KRX 종목코드와 종목명을 구글 시트에 업데이트"""
        try:
            print("구글 시트 서비스 초기화 중...")
            # 구글 시트 서비스 초기화
            
            sheet_service = GoogleSheetService(credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS)
            
            # 스프레드시트 URL로 열기
            sheet_url = "https://docs.google.com/spreadsheets/d/1AgbEpblhoqSBTmryDjSSraqc5lRdgWKNwBUA4VYk2P4/edit"
            print(f"스프레드시트 열기: {sheet_url}")
            
            # 시트 이름을 지정하거나 기본 시트 사용
            worksheet_name = "섹터" # 원하는 시트 이름으로 변경하세요
            try:
                worksheet = sheet_service.open_sheet_by_url(sheet_url, worksheet_name=worksheet_name)
                print(f"'{worksheet_name}' 워크시트 열기 성공")
            except Exception as e:
                logger.warning(f"'{worksheet_name}' 워크시트를 찾을 수 없어 첫 번째 시트를 사용합니다: {str(e)}")
                worksheet = sheet_service.open_sheet_by_url(sheet_url)
            
            # KRX 종목 데이터 가져오기
            print("KRX 종목 정보 가져오는 중...")
            krx_data = await self.read_krx_code()
            print(f"총 {len(krx_data)} 개의 종목 정보를 가져왔습니다.")
            
            # KRX 데이터를 딕셔너리로 변환 (종목코드를 키로)
            krx_dict = {}
            for _, row in krx_data.iterrows():
                krx_dict[row["code"]] = {
                    "name": row["name"]
                }
            
            # 시트 데이터 가져오기
            print("구글 시트 데이터 가져오는 중...")
            all_values = worksheet.get_all_values()
            print(f"구글 시트에서 {len(all_values)} 행의 데이터를 가져왔습니다.")
            
            # 헤더 행이 없으면 추가
            if not all_values:
                print("시트가 비어있어 헤더 행을 추가합니다.")
                worksheet.append_row(["종목코드", "종목명", "섹터"])
                all_values = [["종목코드", "종목명", "섹터"]]
            
            # 시트 데이터를 종목코드를 키로 하는 딕셔너리로 변환
            sheet_dict = {}
            header_row = all_values[0]
            print(f"시트 헤더: {header_row}")
            
            # 종목코드, 종목명, 섹터 컬럼 인덱스 찾기
            code_idx = header_row.index("종목코드") if "종목코드" in header_row else 0
            name_idx = header_row.index("종목명") if "종목명" in header_row else 1
            sector_idx = header_row.index("섹터") if "섹터" in header_row else 2
            print(f"컬럼 인덱스 - 종목코드: {code_idx}, 종목명: {name_idx}, 섹터: {sector_idx}")
            
            # 헤더 제외한 데이터 행만 처리
            for i, row in enumerate(all_values[1:], 2):  # i는 스프레드시트의 행 번호(2부터 시작, 1은 헤더)
                if row and len(row) > code_idx and row[code_idx]:  # 비어있지 않은 행만 처리
                    stock_code = row[code_idx]
                    sheet_dict[stock_code] = {
                        "name": row[name_idx] if len(row) > name_idx else "",
                        "sector": row[sector_idx] if len(row) > sector_idx else "",
                        "row": i  # 시트에서의 행 번호 저장 (1부터 시작)
                    }
            
            print(f"구글 시트에서 {len(sheet_dict)} 개의 종목 정보를 가져왔습니다.")
            
            # 1. 종목명 변경 업데이트
            name_changes = []
            for code, data in sheet_dict.items():
                if code in krx_dict and krx_dict[code]["name"] != data["name"]:
                    name_changes.append({
                        "code": code,
                        "old_name": data["name"],
                        "new_name": krx_dict[code]["name"],
                        "row": data["row"]
                    })
            
            # 종목명 변경 처리
            if name_changes:
                print(f"{len(name_changes)}개 종목의 이름이 변경되었습니다. 업데이트 중...")
                for change in name_changes:
                    worksheet.update_cell(change["row"], name_idx + 1, change["new_name"])  # 0-인덱스를 1-인덱스로 변환(gspread는 1부터 시작)
                    print(f"종목명 변경: {change['code']} - {change['old_name']} → {change['new_name']}")
            else:
                print("변경된 종목명이 없습니다.")
            
            # 2. 상장 폐지된 종목 찾기 - 시트에는 있지만 KRX에는 없는 종목
            delisted = []
            for code, data in sheet_dict.items():
                if code not in krx_dict:
                    delisted.append({
                        "code": code,
                        "name": data["name"],
                        "row": data["row"]
                    })
            
            # 상장 폐지 종목 처리 - 행 번호 역순으로 정렬하여 삭제 (높은 행 번호부터 삭제해야 인덱스 변화가 없음)
            if delisted:
                delisted.sort(key=lambda x: x["row"], reverse=True)
                print(f"{len(delisted)}개 종목이 상장 폐지되었습니다. 시트에서 삭제 중...")
                for item in delisted:
                    worksheet.delete_rows(item["row"])
                    print(f"상장 폐지 종목 삭제: {item['code']} - {item['name']}")
            else:
                print("상장 폐지된 종목이 없습니다.")
            
            # 3. 신규 상장 종목 찾기 - KRX에는 있지만 시트에는 없는 종목
            new_listings = []
            for code, data in krx_dict.items():
                # KOSPI, KOSDAQ은 추가하지 않음
                if code not in sheet_dict and code not in ["KOSPI", "KOSDAQ"]:
                    new_listings.append({
                        "code": code,
                        "name": data["name"]
                    })
            
            # 신규 상장 종목 처리 - 맨 아래에 추가
            if new_listings:
                print(f"{len(new_listings)}개의 신규 상장 종목을 추가합니다.")
                for item in new_listings:
                    # 종목코드, 종목명, 섹터(빈 값)
                    worksheet.append_row([item["code"], item["name"], ""])
                    print(f"신규 상장 종목 추가: {item['code']} - {item['name']}")
            else:
                print("신규 상장 종목이 없습니다.")
            
            print("KRX 종목코드와 종목명 업데이트 완료")
            print(f"시트 URL: {sheet_url}")
            print(f"총 처리결과: 종목명 변경 {len(name_changes)}개, 상장 폐지 {len(delisted)}개, 신규 상장 {len(new_listings)}개")
        except Exception as e:
            logger.error(f"구글 시트 업데이트 중 오류 발생: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise