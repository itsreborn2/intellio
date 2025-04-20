"""
재무 데이터 서비스 클래스

이 모듈은 종목 코드에 대한 재무 데이터를 조회하고 처리하기 위한 서비스를 제공합니다.
GCS에서 PDF 파일을 관리하고 처리하는 로직을 포함합니다.
"""

import os
import json
import asyncio
import logging
from pprint import pprint
import warnings
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, List, Any, Optional, Tuple, Union
import re
from pathlib import Path
from decimal import Decimal

from google.cloud import storage
from common.services.storage import GoogleCloudStorageService
from common.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

import fitz  # PyMuPDF 라이브러리
import pdfplumber  # pdfplumber 추가

from common.core.database import get_db
from stockeasy.repositories.financial_repository import FinancialRepository
from stockeasy.services.financial.pdf_extractor import FinancialPDFExtractor
from stockeasy.services.llm_service import FinancialLLMService
from stockeasy.utils.cache_util import FinancialCacheUtil, cached
from sqlalchemy import select, and_
from stockeasy.models.financial_data import SummaryFinancialData
from stockeasy.models.financial_reports import FinancialReport
from stockeasy.models.income_statement_data import IncomeStatementData
from stockeasy.models.balance_sheet_data import BalanceSheetData
from stockeasy.models.cash_flow_data import CashFlowData
from stockeasy.models.equity_change_data import EquityChangeData

# PDF 관련 모든 경고 메시지 숨기기
warnings.filterwarnings('ignore', category=UserWarning, module='pdfminer')
warnings.filterwarnings('ignore', category=UserWarning, module='pdfplumber')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력용 핸들러
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정
logging.getLogger("pdfminer").setLevel(logging.ERROR)

class FinancialDataService:
    """재무 데이터 서비스 클래스"""
    
    def __init__(self, db_session: AsyncSession = None):
        """서비스 초기화"""
        self._db = db_session
        
        # 로거 초기화 메시지 출력
        logger.info("FinancialDataService 초기화 중...")
        
        self.storage_service = GoogleCloudStorageService(
            project_id=settings.GOOGLE_CLOUD_PROJECT,
            bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
            credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        
        # 경로 설정
        self.base_gcs_path = "Stockeasy/classified/정기보고서"
        self.local_cache_dir = Path(settings.STOCKEASY_LOCAL_CACHE_DIR) / "financial_reports"
        self.file_list_cache_path = Path(settings.STOCKEASY_LOCAL_CACHE_DIR) / "financial_reports_list.json"
        
        # 캐시 디렉토리 생성
        os.makedirs(self.local_cache_dir, exist_ok=True)
        
        # 파일 목록 캐시 만료 시간 (24시간)
        self.cache_expiry = 24 * 60 * 60  # 초 단위
        
        # 메모리 캐시 초기화
        self._file_list_cache = {}  # {stock_code: {"data": [...], "timestamp": datetime}}
        self._last_cache_write = None
        
        # 보고서 유형 매핑
        self.report_type_map = {
            "Q1": "1분기",
            "Q3": "3분기",
            "semiannual": "반기",
            "annual": "연간"
        }
        
        self.pdf_extractor = FinancialPDFExtractor()
        self.llm_service = FinancialLLMService()
        self.cache_util = FinancialCacheUtil()
        
        logger.info("FinancialDataService 초기화 완료")
        
    @property
    async def db(self) -> AsyncSession:
        """데이터베이스 세션 가져오기"""
        if self._db is None:
            async with get_db() as session:
                self._db = session
                return self._db
        return self._db
    
    @property
    async def repository(self) -> FinancialRepository:
        """저장소 인스턴스 가져오기"""
        db = await self.db
        return FinancialRepository(db)
    
    async def get_financial_data(self, stock_code: str, date_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """
        주어진 종목 코드에 대한 재무 데이터를 가져옵니다.
        
        Args:
            stock_code: 종목 코드
            date_range: 데이터를 가져올 날짜 범위 (start_date, end_date)
            
        Returns:
            재무 데이터를 포함하는 딕셔너리
        """
        try:
            # 날짜 범위가 제공되지 않은 경우 기본값 설정 (최근 2년)
            if date_range is None:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=2*365)  # 기본 2년
            else:
                start_date = date_range.get("start_date")
                end_date = date_range.get("end_date")
            
            print(f"재무 데이터 조회: {stock_code}, 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            
            # 1. 파일 목록 가져오기
            file_list = await self._get_file_list(stock_code)
            
            # 2. 파일 목록 필터링 (날짜 기준)
            filtered_files = []
            for file in file_list:
                file_date_str = file.get("date", "")
                #print(f"file.get: {file_date_str}")
                try:
                    file_date = datetime.fromisoformat(file_date_str) if file_date_str else None
                except ValueError:
                    # 날짜 형식이 잘못된 경우 연도만 사용
                    year = file.get("year", 0)
                    if year > 0:
                        file_date = datetime(year, 1, 1)
                    else:
                        file_date = None
                
                #print(f"filedate type : {type(file_date)}, {type(start_date)}, {type(end_date)}")
                # 날짜 또는 연도 기반으로 필터링
                if file_date and start_date <= file_date <= end_date:
                    print(f"append file_date: {file_date}")
                    filtered_files.append(file)
                # elif file.get("year", 0) >= start_date.year and file.get("year", 0) <= end_date.year:
                #     print(f"append file_date2: {file_date}")
                #     filtered_files.append(file)
            
            if not filtered_files:
                logger.warning(f"지정 기간 내 재무 보고서가 없습니다: {stock_code}, 기간: {start_date} ~ {end_date}")
                return {}
                
            # 로그는 한글로 작성
            print(f"조회 기간 내 재무 보고서 {len(filtered_files)}개 찾았습니다: {stock_code}")
            
            # 3. 각 파일에서 데이터 추출
            financial_data = {}
            for file_info in filtered_files:
                # PDF에서 재무제표 페이지 추출
                file_path = file_info.get("file_path")
                local_path = await self._ensure_local_file(file_path)
                
                if local_path:
                    # 페이지 추출 및 데이터 추가
                    financial_statement_pages = await self._extract_financial_statement_pages(local_path)
                    if financial_statement_pages:
                        report_type = file_info.get("type", "unknown")
                        report_year = file_info.get("year", 0)
                        
                        # 데이터 구조화
                        financial_data[f"{report_year}_{report_type}"] = {
                            "content": financial_statement_pages,
                            "metadata": {
                                "year": report_year,
                                "type": report_type,
                                "file_name": os.path.basename(file_path),
                                "date": file_info.get("date", "")
                            }
                        }
            
            # 4. 데이터를 시간 순으로 정렬하여 반환
            sorted_data = dict(sorted(
                financial_data.items(),
                key=lambda x: (x[1]["metadata"]["year"], x[1]["metadata"]["type"]),
                reverse=True  # 최신 데이터 우선
            ))
            
            return {
                "stock_code": stock_code,
                "reports": sorted_data,
                "date_range": {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d")
                }
            }
            
        except Exception as e:
            logger.exception(f"재무 데이터 조회 중 오류: {str(e)}")
            return {}
    
    async def get_financial_revenue_breakdown(self, stock_code: str, date_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """
        주어진 종목 코드에 대한 재무 데이터를 가져옵니다.
        
        Args:
            stock_code: 종목 코드
            date_range: 데이터를 가져올 날짜 범위 (start_date, end_date)
            
        Returns:
            재무 데이터를 포함하는 딕셔너리
        """
        try:
            # 날짜 범위가 제공되지 않은 경우 기본값 설정 (최근 2년)
            if date_range is None:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=2*365)  # 기본 2년
            else:
                start_date = date_range.get("start_date")
                end_date = date_range.get("end_date")
            
            print(f"재무 데이터 조회: {stock_code}, 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            
            # 1. 파일 목록 가져오기
            file_list = await self._get_file_list(stock_code)
            
            # 2. 파일 목록 필터링 (날짜 기준)
            filtered_files = []
            for file in file_list:
                file_date_str = file.get("date", "")
                #print(f"file.get: {file_date_str}")
                try:
                    file_date = datetime.fromisoformat(file_date_str) if file_date_str else None
                except ValueError:
                    # 날짜 형식이 잘못된 경우 연도만 사용
                    year = file.get("year", 0)
                    if year > 0:
                        file_date = datetime(year, 1, 1)
                    else:
                        file_date = None
                
                #print(f"filedate type : {type(file_date)}, {type(start_date)}, {type(end_date)}")
                # 날짜 또는 연도 기반으로 필터링
                if file_date and start_date <= file_date <= end_date:
                    print(f"append file_date: {file_date}")
                    filtered_files.append(file)
                # elif file.get("year", 0) >= start_date.year and file.get("year", 0) <= end_date.year:
                #     print(f"append file_date2: {file_date}")
                #     filtered_files.append(file)
            
            if not filtered_files:
                logger.warning(f"지정 기간 내 재무 보고서가 없습니다: {stock_code}, 기간: {start_date} ~ {end_date}")
                return {}
                
            # 로그는 한글로 작성
            print(f"조회 기간 내 재무 보고서 {len(filtered_files)}개 찾았습니다: {stock_code}")
            
            # 3. 각 파일에서 데이터 추출
            revenue_breakdown_data = ""
            for file_info in filtered_files:
                # PDF에서 재무제표 페이지 추출
                file_path = file_info.get("file_path")
                local_path = await self._ensure_local_file(file_path)
                
                if local_path:
                    # 페이지 추출 및 데이터 추가
                    extracted_data = await self.extract_revenue_breakdown_data(local_path)
                    if extracted_data:  # None이나 빈 문자열이 아닌 경우에만 추가
                        revenue_breakdown_data += extracted_data

            return revenue_breakdown_data
            
        except Exception as e:
            logger.exception(f"재무 데이터 조회 중 오류: {str(e)}")
            return {}
            
    async def _get_file_list(self, stock_code: str) -> List[Dict[str, Any]]:
        """
        주어진 종목 코드에 대한 GCS 파일 목록을 가져옵니다.
        메모리 캐시 -> 파일 캐시 -> GCS 순으로 조회합니다.
        
        Args:
            stock_code: 종목 코드
            
        Returns:
            파일 경로 목록
        """
        now = datetime.now()
        
        # 1. 메모리 캐시 확인
        if stock_code in self._file_list_cache:
            cache_entry = self._file_list_cache[stock_code]
            if (now - cache_entry["timestamp"]).total_seconds() < self.cache_expiry:
                print(f"Using memory cached file list for stock {stock_code}")
                return cache_entry["data"]
        
        # 2. 파일 캐시 확인
        if await self._is_file_list_cache_valid(stock_code):
            try:
                with open(self.file_list_cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    if stock_code in cached_data:
                        # 메모리 캐시 업데이트
                        self._file_list_cache[stock_code] = {
                            "data": cached_data[stock_code],
                            "timestamp": now
                        }
                        print(f"Using file cached list for stock {stock_code}")
                        return cached_data[stock_code]
            except Exception as e:
                logger.warning(f"Failed to load cached file list: {str(e)}")
        
        # 3. GCS에서 파일 목록 가져오기
        print(f"Retrieving file list from GCS for stock {stock_code}")
        
        prefix = f"{self.base_gcs_path}/{stock_code}/"
        blobs = list(self.storage_service.bucket.list_blobs(prefix=prefix))
        
        file_list = []
        for blob in blobs:
            file_info = self._parse_filename(blob.name)
            if file_info:
                file_list.append({
                    "file_path": blob.name,
                    **file_info
                })
        
        # 메모리 캐시 업데이트
        self._file_list_cache[stock_code] = {
            "data": file_list,
            "timestamp": now
        }
        
        # 파일 캐시 업데이트 (다른 종목의 캐시도 보존)
        await self._update_file_list_cache(stock_code, file_list)
        
        return file_list
        
    async def _is_file_list_cache_valid(self, stock_code: str) -> bool:
        """
        파일 목록 캐시가 유효한지 확인합니다.
        종목 코드별로 캐시 타임스탬프를 관리하여 개별 종목의 업데이트를 추적합니다.
        
        Args:
            stock_code: 종목 코드
            
        Returns:
            캐시가 유효하면 True, 그렇지 않으면 False
        """
        print(f"캐시 파일 유효성 검사 시작: {self.file_list_cache_path} (종목: {stock_code})")
        
        if not os.path.exists(self.file_list_cache_path):
            print("캐시 파일이 존재하지 않습니다. 유효하지 않음.")
            return False
            
        now = datetime.now()
        
        # 메모리 캐시 확인
        if stock_code in self._file_list_cache:
            cache_entry = self._file_list_cache[stock_code]
            time_diff = (now - cache_entry["timestamp"]).total_seconds()
            is_valid = time_diff < self.cache_expiry
            print(f"메모리에 저장된 종목({stock_code})의 마지막 캐시 갱신 시간: {cache_entry['timestamp']}")
            print(f"경과 시간: {time_diff:.1f}초, 만료 시간: {self.cache_expiry}초, 유효함: {is_valid}")
            return is_valid
            
        # 파일 캐시 확인
        try:
            with open(self.file_list_cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # 종목별 타임스탬프 확인
            if '_timestamps' in cache_data and stock_code in cache_data['_timestamps']:
                # 타임스탬프 문자열을 datetime으로 변환
                timestamp_str = cache_data['_timestamps'][stock_code]
                timestamp = datetime.fromisoformat(timestamp_str)
                time_diff = (now - timestamp).total_seconds()
                is_valid = time_diff < self.cache_expiry
                print(f"파일 캐시에 저장된 종목({stock_code})의 마지막 갱신 시간: {timestamp}")
                print(f"경과 시간: {time_diff:.1f}초, 만료 시간: {self.cache_expiry}초, 유효함: {is_valid}")
                return is_valid
            else:
                print(f"종목({stock_code})에 대한 타임스탬프 정보가 없습니다. 유효하지 않음.")
                return False
                
        except Exception as e:
            print(f"캐시 파일 읽기 오류: {str(e)}")
            return False
        
    async def _update_file_list_cache(self, stock_code: str, file_list: List[Dict[str, Any]]) -> None:
        """
        파일 목록 캐시를 업데이트합니다.
        종목 코드별로 타임스탬프를 관리합니다.
        
        Args:
            stock_code: 종목 코드
            file_list: 업데이트할 파일 목록
        """
        try:
            # 기존 캐시 데이터 로드
            cached_data = {}
            if os.path.exists(self.file_list_cache_path):
                with open(self.file_list_cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
            
            # 타임스탬프 관리 구조 초기화
            if '_timestamps' not in cached_data:
                cached_data['_timestamps'] = {}
                
            # 현재 시간을 타임스탬프로 저장
            now = datetime.now()
            cached_data['_timestamps'][stock_code] = now.isoformat()
            
            # 새 데이터 추가/업데이트
            cached_data[stock_code] = file_list
            
            # 캐시 파일 저장
            with open(self.file_list_cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, ensure_ascii=False, indent=2)
            
            # 메모리 캐시 업데이트
            self._file_list_cache[stock_code] = {
                "data": file_list,
                "timestamp": now
            }
            
            print(f"종목({stock_code})의 파일 목록 캐시가 갱신되었습니다. 타임스탬프: {now.isoformat()}")
            
        except Exception as e:
            logger.warning(f"Failed to update file list cache: {str(e)}")
            print(f"파일 목록 캐시 업데이트 실패: {str(e)}")
            
    def _parse_filename(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        파일명을 파싱하여 보고서 정보를 추출합니다.
        
        예: 정기보고서/005930/20241114_삼성전자_005930_전기·전자_Q3_DART.pdf
        
        Args:
            file_path: 파일 경로
            
        Returns:
            추출된 정보를 포함하는 딕셔너리 또는 None
        """
        try:
            # 파일명만 추출
            file_name = os.path.basename(file_path)
            
            # 정규식 패턴: 날짜_회사명_종목코드_업종_보고서유형_DART.pdf
            pattern = r"(\d{8})_(.+)_(\d{6})_(.+)_(.+)_DART\.pdf"
            match = re.match(pattern, file_name)
            
            if not match:
                logger.warning(f"Could not parse filename: {file_name}")
                return None
                
            date_str, company_name, stock_code, industry, report_type = match.groups()
            
            # 날짜 형식 변환
            try:
                date = datetime.strptime(date_str, "%Y%m%d")
                formatted_date = date.strftime("%Y-%m-%d")
                year = date.year
                if report_type.lower() == "annual":
                    year = date.year -1
            except ValueError:
                logger.warning(f"Invalid date format in filename: {date_str}")
                year = int(date_str[:4]) if len(date_str) >= 4 else 0
                formatted_date = date_str
            
            return {
                "date": formatted_date,
                "year": year,
                "company": company_name,
                "stock_code": stock_code,
                "industry": industry,
                "type": report_type
            }
            
        except Exception as e:
            logger.warning(f"Error parsing filename {file_path}: {str(e)}")
            return None
            
    async def _ensure_local_file(self, gcs_path: str) -> Optional[str]:
        """
        GCS 파일을 로컬에 캐싱합니다. 이미 존재하면 로컬 경로를 반환합니다.
        
        Args:
            gcs_path: GCS 파일 경로
            
        Returns:
            로컬 파일 경로 또는 None (실패 시)
        """
        try:
            # GCS 경로에서 상대 경로 추출 (Stockeasy/classified/정기보고서/종목코드/파일명)
            relative_path = gcs_path.split('/', 2)[-1]  # '정기보고서/종목코드/파일명' 부분만 추출
            
            # 로컬 캐시 경로 생성
            local_path = self.local_cache_dir / relative_path
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 파일이 이미 존재하는지 확인
            if os.path.exists(local_path):
                logger.info(f"Using cached file: {local_path}")
                return str(local_path)
                
            # GCS에서 파일 다운로드
            logger.info(f"Downloading file from GCS: {gcs_path}")
            content = await self.storage_service.download_file(gcs_path)
            
            # 로컬에 저장
            with open(local_path, 'wb') as f:
                f.write(content)
                
            logger.info(f"Downloaded and cached file: {local_path}")
            return str(local_path)
            
        except Exception as e:
            logger.exception(f"Error ensuring local file for {gcs_path}: {str(e)}")
            return None
            
    async def _extract_financial_statement_pages(self, pdf_path: str) -> str:
        """
        PDF에서 재무제표 페이지를 추출합니다.
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            추출된 재무제표 페이지 텍스트
        """
        try:
            loop = asyncio.get_event_loop()
            fs_pages = []
            # keywords = ["연결재무상태표", "연결손익계산서", "연결포괄손익계산서", 
            #           "연결현금흐름표", "재무상태표", "손익계산서", "포괄손익계산서",
            #           "재무에 관한 사항", "연결재무제표", "요약재무정보"]
            keywords = ["요약재무정보"]
            
            # 1. fitz로 목차 페이지 찾기
            doc = await loop.run_in_executor(None, partial(fitz.open, pdf_path))
            target_pages = set()
            
            try:
                # 목차 정보 가져오기
                toc = await loop.run_in_executor(None, doc.get_toc)
                logger.info(f"Found TOC with {len(toc)} items")
                
                # 목차에서 재무제표 관련 페이지 찾기
                for item in toc:
                    level, title, page_num = item
                    if any(keyword in title for keyword in keywords):
                        # PDF 페이지 번호는 0-based로 변환
                        target_page = page_num - 1
                        if 0 <= target_page < len(doc):
                            # 현재 페이지와 뒤따르는 2페이지 추가
                            for i in range(3):  # 현재 페이지 포함 3페이지
                                check_page = target_page + i
                                if 0 <= check_page < len(doc):
                                    target_pages.add(check_page)
                                    # if i == 0:
                                    #     logger.info(f"Found financial section '{title}' at page {page_num}")
                                    # else:
                                    #     logger.info(f"Adding following page {check_page + 1} for section '{title}'")
                
                # 목차에서 페이지를 찾지 못한 경우 키워드로 검색
                if not target_pages:
                    logger.info("No pages found in TOC, searching by keywords...")
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        text = await loop.run_in_executor(None, page.get_text)
                        if any(keyword in text for keyword in keywords):
                            # 키워드가 발견된 페이지와 뒤따르는 2페이지 추가
                            for i in range(3):  # 현재 페이지 포함 3페이지
                                check_page = page_num + i
                                if 0 <= check_page < len(doc):
                                    target_pages.add(check_page)
                                    # if i == 0:
                                    #     logger.info(f"Found financial statement at page {page_num + 1}")
                                    # else:
                                    #     logger.info(f"Adding following page {check_page + 1}")
            
            finally:
                await loop.run_in_executor(None, doc.close)
            
            # 2. pdfplumber로 찾은 페이지의 내용 추출
            if target_pages:
                # pdfplumber를 동기 방식으로 사용
                pdf = await loop.run_in_executor(None, pdfplumber.open, pdf_path)
                try:
                    for page_num in sorted(target_pages):
                        page = await loop.run_in_executor(None, lambda: pdf.pages[page_num])
                        text = await loop.run_in_executor(None, page.extract_text)
                        if text.strip():  # 빈 페이지가 아닌 경우만 추가
                            fs_pages.append((page_num, text))
                finally:
                    await loop.run_in_executor(None, pdf.close)
                            
                # 페이지 번호 순으로 정렬
                fs_pages.sort(key=lambda x: x[0])
                
                # 추출된 텍스트 반환
                logger.info(f"Extracted {len(fs_pages)} pages from {pdf_path}")
                return "\n\n------- 페이지 구분선 -------\n\n".join([text for _, text in fs_pages])
            
            logger.warning(f"No financial statement pages found in {pdf_path}")
            return ""
                
        except Exception as e:
            logger.exception(f"Error extracting financial statement pages from {pdf_path}: {str(e)}")
            return "" 
        
    async def extract_revenue_breakdown_data(self, target_report: str):
        """
        주어진 사업보고서 파일에서 매출 및 수주 현황 정보를 추출합니다.
        
        Args:
            target_report: 사업보고서 파일 경로
        return :
            매출 및 수주상황 섹션 텍스트 
        """
        try:
            base_file_name = os.path.basename(target_report)
            #logger.info(f" 사업보고서: {base_file_name}")
            #  20250320_메지온_140410_일반서비스_annual_DART.pdf
            year = base_file_name.split("_")[0]
            year = year[:4]
            quater_file = base_file_name.split("_")[4]
            if quater_file == "annual":
                year = int(year) - 1
            report_type_map = {
                    "Q1": "1분기",
                    "Q3": "3분기",
                    "semiannual": "2분기",
                    "annual": "4분기"
                }
            
            quater = report_type_map[quater_file]

            # 3. fitz를 사용하여 목차 내용 추출
            doc = fitz.open(target_report)
            toc = doc.get_toc()  # 목차 가져오기
            #print(f"toc: {len(toc)}")
            if not toc:
                logger.error("목차를 찾을 수 없습니다.")
                return ""
            
            # 4. 목차에서 'II. 사업의 내용' 및 '매출 및 수주상황' 찾기
            business_content_start_page = None
            business_content_end_page = None
            sales_section_start_page = None
            sales_section_end_page = None
            
            for i, item in enumerate(toc):
                level, title, page_num = item
                
                # 'II. 사업의 내용' 목차 찾기
                if "사업의 내용" in title and (title.startswith("II.") or title.startswith("Ⅱ.")):
                    business_content_start_page = page_num - 1  # 0-based 페이지 번호로 변환
                    
                    # 다음 대분류 목차를 찾아 끝 페이지 결정
                    for next_item in toc[i+1:]:
                        next_level, next_title, next_page = next_item
                        if next_level <= level and (next_title.startswith("III.") or next_title.startswith("Ⅲ.") or 
                                                next_title.startswith("IV.") or next_title.startswith("Ⅳ.")):
                            business_content_end_page = next_page - 2  # 다음 대분류 시작 전 페이지
                            break
                    
                    # 다음 대분류가 없으면 문서 끝까지를 범위로 설정
                    if business_content_end_page is None:
                        business_content_end_page = len(doc) - 1
                
                # '매출 및 수주상황' 목차 찾기 (II. 사업의 내용 아래에 있어야 함)
                if business_content_start_page is not None and "매출" in title and "수주" in title:
                    sales_section_start_page = page_num - 1  # 0-based 페이지 번호로 변환
                    
                    # 다음 동일 레벨 또는 상위 레벨 목차를 찾아 끝 페이지 결정
                    for next_item in toc[i+1:]:
                        next_level, next_title, next_page = next_item
                        if next_level <= level:
                            sales_section_end_page = next_page - 2  # 다음 섹션 시작 전 페이지
                            break
                    
                    # 다음 섹션이 없으면 사업의 내용 끝까지를 범위로 설정
                    if sales_section_end_page is None and business_content_end_page is not None:
                        sales_section_end_page = business_content_end_page
                    
                    break  # 매출 및 수주상황 섹션을 찾았으므로 검색 종료
            
            # 5. 페이지 범위 결정 (매출 및 수주상황을 찾지 못했다면 사업의 내용 전체를 사용)
            if sales_section_start_page is not None and sales_section_end_page is not None:
                start_page = sales_section_start_page
                end_page = sales_section_end_page
                #logger.info(f"'매출 및 수주상황' 섹션을 찾았습니다: 페이지 {start_page+1}~{end_page+1}")
            elif business_content_start_page is not None and business_content_end_page is not None:
                start_page = business_content_start_page
                end_page = business_content_end_page
                #logger.info(f"'II. 사업의 내용' 섹션을 찾았습니다: 페이지 {start_page+1}~{end_page+1}")
            else:
                logger.error("매출 및 수주상황, 사업의 내용 섹션을 찾을 수 없습니다.")
                return ""
            
            # 6. pdfplumber를 사용하여 해당 페이지 내용 추출
            extracted_text = f"-----------------------------\n\n"
            extracted_text += f"## {year}년 {quater} 데이터\n\n"
            #print(f"{extracted_text}")
            with pdfplumber.open(target_report) as pdf:
                # 페이지 범위가 너무 크면 최대 10페이지로 제한
                max_pages = 30
                if end_page - start_page > max_pages:
                    logger.warning(f"페이지 범위가 너무 큽니다. 처음 {max_pages}페이지만 추출합니다.")
                    end_page = start_page + max_pages
                
                for page_num in range(start_page, end_page + 1):
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        text = page.extract_text()
                        if text:
                            extracted_text += f"\n\n--- 페이지 {page_num + 1} ---\n\n{text}"
            
            extracted_text += f"\n\n--- 데이터 끝 ---\n\n"
            if not extracted_text:
                logger.error("추출된 텍스트가 없습니다.")
                return ""
            return extracted_text
        except Exception as e:
            logger.exception(f"Error extracting revenue breakdown data: {str(e)}")
            return ""
        finally:
            doc.close()
    
    async def process_financial_summary(
        self, company_code: str, report_file_path: str, report_type: str,
        report_year: int, report_quarter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        연결 포괄손익계산서 처리 파이프라인
        
        Args:
            company_code: 기업 코드
            report_file_path: 보고서 파일 경로
            report_type: 보고서 유형 (annual, semi, quarter)
            report_year: 보고서 연도
            report_quarter: 보고서 분기
            
        Returns:
            처리 결과
        """
        start_time = datetime.now()
        logger.info(f"연결 포괄손익계산서 처리 시작: 기업={company_code}, 연도={report_year}, 분기={report_quarter or '연간'}, 파일={os.path.basename(report_file_path)}")
        
        try:
            # 파일 유효성 검사
            if not os.path.exists(report_file_path):
                logger.error(f"파일이 존재하지 않습니다: {report_file_path}")
                return {
                    "success": False,
                    "message": f"파일이 존재하지 않습니다: {report_file_path}"
                }
            
            # 회사 정보 조회
            logger.info(f"기업 정보 조회 중: {company_code}")
            repo = await self.repository
            company = await repo.get_company_by_code(company_code)
            
            if not company:
                logger.error(f"회사 정보가 없습니다: {company_code}")
                return {
                    "success": False,
                    "message": f"회사 정보가 없습니다: {company_code}"
                }
            logger.info(f"기업 정보 조회 완료: ID={company.id}, 이름={company.company_name}")
            
            # 보고서 정보 조회 또는 생성
            logger.info(f"보고서 정보 조회/생성 중: {company_code}, {report_year}년 {report_quarter or '연간'}")
            report = await repo.get_or_create_financial_report(
                company_id=company.id,
                report_type=report_type,
                report_year=report_year,
                report_quarter=report_quarter,
                file_path=report_file_path
            )
            logger.info(f"보고서 정보 준비 완료: ID={report.id}, 타입={report_type}")
            
            # 1. 재무제표 페이지 범위 찾기
            logger.info(f"PDF 페이지 범위 탐색 시작: {os.path.basename(report_file_path)}")
            
            # PDF 문서 열기
            doc = fitz.open(report_file_path)
            toc = doc.get_toc()
            logger.info(f"목차\n{toc}")
            
            # 연결 포괄손익계산서 관련 키워드
            income_statement_keywords = [
                "연결 포괄손익계산서", "연결포괄손익계산서", 
                "연결 손익계산서", "연결손익계산서",
                "포괄손익계산서", "손익계산서"
            ]
            
            # 재무제표 섹션 키워드
            financial_statement_keywords = [
                "연결 재무제표", "연결재무제표",
                "재무제표"
            ]
            
            # 각 재무제표 유형 키워드
            statement_type_keywords = {
                "balance_sheet": ["재무상태표", "연결재무상태표", "연결 재무상태표"],
                "income_statement": ["손익계산서", "연결손익계산서", "연결 손익계산서", "포괄손익계산서", "연결포괄손익계산서", "연결 포괄손익계산서"],
                "cash_flow": ["현금흐름표", "연결현금흐름표", "연결 현금흐름표"],
                "equity_change": ["자본변동표", "연결자본변동표", "연결 자본변동표"]
            }
            
            # 1. 목차에서 손익계산서 섹션 직접 찾기
            start_page = None
            end_page = None
            
            for i, item in enumerate(toc):
                level, title, page = item
                
                for keyword in income_statement_keywords:
                    if keyword in title:
                        # 시작 페이지 설정 (목차의 페이지는 1부터 시작하지만 fitz는 0부터 시작)
                        start_page = page - 1
                        
                        # 다음 동일 레벨 또는 상위 레벨 목차 항목 찾기
                        for next_item in toc[i+1:]:
                            next_level, next_title, next_page = next_item
                            if next_level <= level:
                                # 다음 섹션 시작 직전 페이지를 끝 페이지로 설정
                                end_page = next_page - 2
                                break
                        
                        # 다음 섹션을 찾지 못한 경우 기본적으로 시작 페이지 + 2로 설정
                        if end_page is None:
                            end_page = min(start_page + 3, len(doc) - 1)
                            
                        logger.info(f"연결 포괄손익계산서 섹션 찾음: 페이지 {start_page+1}~{end_page+1}")
                        break
                
                if start_page is not None:
                    break
            
            # 2. 손익계산서 섹션을 찾지 못한 경우, 연결 재무제표 섹션 찾기
            financial_statement_page = None
            
            if start_page is None:
                logger.info("손익계산서 섹션을 찾지 못했습니다. 연결 재무제표 섹션 찾기 시도...")
                
                for i, item in enumerate(toc):
                    level, title, page = item
                    
                    for keyword in financial_statement_keywords:
                        if keyword in title:
                            financial_statement_page = page - 1
                            logger.info(f"연결 재무제표 섹션 찾음: 페이지 {financial_statement_page+1}")
                            break
                    
                    if financial_statement_page is not None:
                        break
                
                # 연결 재무제표 섹션 이후 10페이지 내에서 손익계산서 찾기
                if financial_statement_page is not None:
                    search_range = 15  # 연결 재무제표 이후 15페이지까지 검색
                    search_end = min(financial_statement_page + search_range, len(doc) - 1)
                    
                    for page_num in range(financial_statement_page, search_end + 1):
                        page = doc[page_num]
                        text = page.get_text()
                        
                        for keyword in income_statement_keywords:
                            if keyword in text:
                                start_page = page_num
                                end_page = min(start_page + 3, len(doc) - 1)  # 기본적으로 3페이지 범위
                                logger.info(f"연결 재무제표 이후에서 손익계산서 찾음: 페이지 {start_page+1}~{end_page+1}")
                                break
                        
                        if start_page is not None:
                            break
            
            # 3. 위 방법으로도 찾지 못한 경우 본문 내용 전체 검색
            if start_page is None:
                logger.info("연결 재무제표 이후에서도 손익계산서를 찾지 못했습니다. 본문 내용 전체 검색...")
                
                for page_num in range(min(100, len(doc))):  # 처음 100페이지만 검색
                    page = doc[page_num]
                    text = page.get_text()
                    
                    for keyword in income_statement_keywords:
                        if keyword in text:
                            start_page = page_num
                            end_page = min(start_page + 3, len(doc) - 1)
                            logger.info(f"본문에서 손익계산서 찾음: 페이지 {start_page+1}~{end_page+1}")
                            break
                    
                    if start_page is not None:
                        break
            
            # 4. 그래도 찾지 못한 경우 오류 반환
            if start_page is None:
                logger.error(f"연결 포괄손익계산서 페이지를 찾을 수 없습니다: {company_code}")
                doc.close()
                return {
                    "success": False,
                    "message": f"연결 포괄손익계산서 페이지를 찾을 수 없습니다: {company_code}"
                }
            doc.close()
            # 2. 페이지 텍스트 추출
            logger.info(f"페이지 텍스트 추출 시작: 페이지 {start_page+1}~{end_page+1}")
            
            all_text = ""
            # fitz 대신 pdfplumber 사용하여 텍스트 추출
            with pdfplumber.open(report_file_path) as pdf:
                for page_num in range(start_page, end_page + 1):
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        text = page.extract_text()
                        if text:
                            all_text += f"\n\n--- 페이지 {page_num + 1} ---\n\n{text}"
            
            if not all_text.strip():
                logger.error(f"연결 포괄손익계산서 텍스트 추출 실패: {company_code}")
                return {
                    "success": False,
                    "message": f"연결 포괄손익계산서 텍스트 추출 실패: {company_code}"
                }
            
            logger.info(f"페이지 텍스트 추출 완료: 텍스트 길이={len(all_text)}자")
            
            # 3. LLM으로 데이터 구조화
            logger.info("LLM을 사용한 데이터 구조화 시작")
            llm_start_time = datetime.now()
            structured_data = await self.llm_service.structure_income_statement_table(all_text)
            llm_duration = (datetime.now() - llm_start_time).total_seconds()
            
            if "error" in structured_data:
                logger.error(f"데이터 구조화에 실패했습니다: {company_code}, 오류: {structured_data.get('error')}")
                return {
                    "success": False,
                    "message": f"데이터 구조화에 실패했습니다: {company_code}",
                    "details": structured_data
                }
            
            financial_items = structured_data.get("financial_summary", [])
            logger.info(f"LLM 데이터 구조화 완료: {len(financial_items)}개 항목 식별, 소요시간={llm_duration:.1f}초")
            pprint(financial_items, indent=4)
            
            # 4. 데이터베이스 저장
            logger.info(f"데이터베이스 저장 시작: 회사={company_code}, 보고서={report.id}")
            save_start_time = datetime.now()
            saved_items = await self._save_structured_data(
                company.id, report.id, structured_data, income_statement_keywords
            )
            save_duration = (datetime.now() - save_start_time).total_seconds()
            logger.info(f"데이터베이스 저장 완료: {len(saved_items)}개 항목 저장, 소요시간={save_duration:.1f}초")
            
            # 5. 보고서 처리 완료 표시
            report.processed = True
            await self._db.commit()
            logger.info(f"보고서 처리 완료 상태로 업데이트: {report.id}")
            
            # 6. 캐시 무효화
            logger.info(f"캐시 무효화 시작: {company_code}")
            await self.cache_util.delete_pattern(f"summary:{company_code}")
            await self.cache_util.delete_pattern("financial")
            logger.info("캐시 무효화 완료")
            
            total_duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"연결 포괄손익계산서 처리 완료: 회사={company_code}, 저장 항목={len(saved_items)}개, 총소요시간={total_duration:.1f}초")
            
            return {
                "success": True,
                "message": f"연결 포괄손익계산서 처리 완료: {company_code}, {report_year}년 {report_quarter or ''}분기",
                "details": {
                    "company_code": company_code,
                    "company_name": company.company_name,
                    "report_type": report_type,
                    "report_year": report_year,
                    "report_quarter": report_quarter,
                    "items_count": len(saved_items),
                    "items": saved_items,
                    "duration_seconds": total_duration
                }
            }
            
        except Exception as e:
            total_duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"연결 포괄손익계산서 처리 중 오류 발생: {company_code}, 오류={str(e)}, 소요시간={total_duration:.1f}초", exc_info=True)
            if self._db:
                await self._db.rollback()
            return {
                "success": False,
                "message": f"연결 포괄손익계산서 처리 중 오류 발생: {str(e)}"
            }
    
    async def _save_structured_data(
        self, company_id: int, report_id: int, structured_data: Dict[str, Any], keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        구조화된 데이터를 데이터베이스에 저장
        
        Args:
            company_id: 회사 ID
            report_id: 보고서 ID
            structured_data: 구조화된 데이터
            keywords: 추출된 키워드 목록
            
        Returns:
            저장된 항목 목록
        """
        repo = await self.repository
        saved_items = []
        
        # 보고서 정보 조회 (현재 연월 확인용)
        report_result = await self._db.execute(
            select(FinancialReport).where(FinancialReport.id == report_id)
        )
        current_report = report_result.scalar_one_or_none()
        
        if not current_report:
            logger.error(f"보고서를 찾을 수 없습니다: ID={report_id}")
            return saved_items
            
        current_year = current_report.report_year
        current_quarter = current_report.report_quarter
        current_year_month = current_report.year_month
        
        logger.info(f"데이터 저장 시작: 연도={current_year}, 분기={current_quarter or '연간'}")
        
        # 재무제표 유형 식별
        statement_type_mapping = self._identify_statement_type(keywords)
        
        # 오류 발생 시 프로그램 중단 플래그
        errors_detected = False
        
        for item in structured_data.get("financial_summary", []):
            if errors_detected:
                break
                
            item_name = item.get("item_name")
            item_code = item.get("item_code")
            
            # 재무제표 유형 결정 (기본값은 item에서 제공한 값, 없으면 키워드에서 식별한 값)
            statement_type = item.get("statement_type", statement_type_mapping["type"])
            
            # 누적 여부 결정 (기본값은 item에서 제공한 값, 없으면 키워드를 기반으로 판단)
            is_cumulative = item.get("is_cumulative", statement_type_mapping["is_cumulative"])
            
            # 아이템 코드 길이 체크 (DB 필드 제한 200자)
            if len(item_code) > 190:  # 안전 마진으로 190자로 제한
                logger.warning(f"아이템 코드가 너무 깁니다: {item_code} ({len(item_code)}자)")
                # 코드 자르기
                short_code = item_code[:190]
                logger.warning(f"아이템 코드를 {short_code}로 줄입니다.")
                item_code = short_code
            
            try:
                # 카테고리 결정
                category = self._determine_category(statement_type, keywords)
                
                # 항목 매핑 조회 또는 생성
                item_mapping = await repo.get_item_mapping_by_code(item_code)
                if not item_mapping:
                    logger.info(f"새 항목 매핑 생성: {item_code}, {item_name}")
                    item_mapping = await repo.create_item_mapping(
                        item_code=item_code,
                        category=category,
                        standard_name=item_name
                    )
                
                # 원본 항목명 매핑 저장 (항목명이 다른 경우에만)
                if item_name != item_mapping.standard_name:
                    await repo.create_raw_mapping(item_mapping.id, item_name)
                
                # 데이터 값 저장
                for value_data in item.get("values", []):
                    data_year = value_data.get("year")
                    data_quarter = value_data.get("quarter")
                    value = value_data.get("value")
                    unit = value_data.get("unit", "원")
                    
                    if value is None:
                        continue
                    
                    # 연월 계산
                    data_year_month = data_year * 100
                    if data_quarter:
                        data_year_month += data_quarter * 3
                    else:
                        data_year_month += 12
                    
                    # 누적 값과 기간 값 계산
                    cumulative_value, period_value = await self._calculate_values(
                        value, is_cumulative, data_year, data_quarter, 
                        company_id, item_mapping.id, statement_type, category
                    )
                    
                    # 재무제표 유형에 따라 적절한 테이블에 저장
                    financial_data = await self._save_to_appropriate_table(
                        report_id, company_id, item_mapping.id, data_year_month,
                        value, unit, cumulative_value, period_value, is_cumulative,
                        statement_type, category, item_name
                    )
                    
                    saved_items.append({
                        "item_code": item_code,
                        "item_name": item_name,
                        "year": data_year,
                        "quarter": data_quarter,
                        "year_month": data_year_month,
                        "value": value,
                        "cumulative_value": cumulative_value,
                        "period_value": period_value,
                        "is_cumulative": is_cumulative,
                        "statement_type": statement_type,
                        "unit": unit,
                        "table": category.lower().replace(" ", "_") + "_data"
                    })
            except Exception as e:
                logger.error(f"항목 저장 중 오류 발생: {item_code}, {item_name}")
                logger.error(f"오류 상세: {str(e)}")
                # 모든 스택 트레이스 로깅
                logger.exception("상세 오류 정보:")
                
                # 임시로 프로그램 중단을 위한 플래그 설정
                errors_detected = True
                
                # 롤백
                await self._db.rollback()
                
                # 오류를 다시 발생시켜 상위 호출자에게 전파
                raise
        
        # 명시적 커밋 (오류가 없는 경우에만)
        if not errors_detected:
            await self._db.commit()
        
        return saved_items
        
    def _identify_statement_type(self, keywords: List[str]) -> Dict[str, Any]:
        """
        키워드 목록을 기반으로 재무제표 유형 식별
        
        Args:
            keywords: 키워드 목록
            
        Returns:
            재무제표 유형 정보 (type, is_cumulative)
        """
        # 재무제표 유형 키워드 매핑
        keyword_mapping = {
            # 요약재무정보 관련 키워드
            "요약재무상태": {"type": "summary", "is_cumulative": False},
            "요약재무정보": {"type": "summary", "is_cumulative": False},
            "요약 재무상태": {"type": "summary", "is_cumulative": False},
            "요약 재무정보": {"type": "summary", "is_cumulative": False},
            
            # 재무상태표 관련 키워드
            "재무상태표": {"type": "balance_sheet", "is_cumulative": False},
            "연결재무상태표": {"type": "balance_sheet", "is_cumulative": False},
            "별도재무상태표": {"type": "balance_sheet", "is_cumulative": False},
            
            # 손익계산서 관련 키워드
            "손익계산서": {"type": "income_statement", "is_cumulative": True},
            "연결손익계산서": {"type": "income_statement", "is_cumulative": True},
            "별도손익계산서": {"type": "income_statement", "is_cumulative": True},
            "포괄손익계산서": {"type": "comprehensive_income", "is_cumulative": True},
            "연결포괄손익계산서": {"type": "comprehensive_income", "is_cumulative": True},
            "별도포괄손익계산서": {"type": "comprehensive_income", "is_cumulative": True},
            
            # 현금흐름표 관련 키워드
            "현금흐름표": {"type": "cash_flow", "is_cumulative": True},
            "연결현금흐름표": {"type": "cash_flow", "is_cumulative": True},
            "별도현금흐름표": {"type": "cash_flow", "is_cumulative": True},
            
            # 자본변동표 관련 키워드
            "자본변동표": {"type": "equity_change", "is_cumulative": False},
            "연결자본변동표": {"type": "equity_change", "is_cumulative": False},
            "별도자본변동표": {"type": "equity_change", "is_cumulative": False}
        }
        
        # 기본값 (요약재무정보)
        default_type = {"type": "summary", "is_cumulative": False}
        
        # 키워드 목록에서 매칭되는 재무제표 유형 찾기
        for keyword in keywords:
            for key, value in keyword_mapping.items():
                if key in keyword:
                    logger.info(f"재무제표 유형 식별: {keyword} -> {value['type']}, 누적여부: {value['is_cumulative']}")
                    return value
        
        # 매칭되는 키워드가 없으면 기본값 반환
        return default_type
        
    def _determine_category(self, statement_type: str, keywords: List[str]) -> str:
        """
        재무제표 유형을 기반으로 카테고리 결정
        
        Args:
            statement_type: 재무제표 유형
            keywords: 키워드 목록
            
        Returns:
            카테고리명
        """
        # 재무제표 유형별 카테고리 매핑
        type_to_category = {
            "summary": "요약재무정보",
            "balance_sheet": "재무상태표",
            "income_statement": "손익계산서",
            "comprehensive_income": "포괄손익계산서",
            "cash_flow": "현금흐름표",
            "equity_change": "자본변동표"
        }
        
        # 연결/별도 여부 확인
        is_consolidated = False
        for keyword in keywords:
            if "연결" in keyword:
                is_consolidated = True
                break
        
        # 카테고리 결정
        base_category = type_to_category.get(statement_type, "요약재무정보")
        if is_consolidated and statement_type != "summary":
            return f"연결{base_category}"
        
        return base_category
        
    async def _calculate_values(self, value, is_cumulative, data_year, data_quarter, 
                              company_id, item_id, statement_type, category) -> Tuple[float, float]:
        """
        누적값과 기간값 계산
        
        Args:
            value: 원본 값
            is_cumulative: 누적 값 여부
            data_year: 데이터 연도
            data_quarter: 데이터 분기
            company_id: 회사 ID
            item_id: 항목 ID
            statement_type: 재무제표 유형
            category: 카테고리
            
        Returns:
            누적값, 기간값 튜플
        """
        # 기본값 설정
        cumulative_value = value
        period_value = value
        
        # 누적 데이터이고 분기 데이터인 경우에만 계산 필요
        if is_cumulative and data_quarter is not None:
            # 1분기인 경우 해당 분기 값 그대로 사용 (회계연도 시작)
            if data_quarter == 1:
                logger.info(f"1분기 데이터: {category}, {data_year}{data_quarter*3:02d}, 값={value}")
                # 1분기는 누적값 = 기간값 = 현재 값
                cumulative_value = value
                period_value = value
            else:
                # 2분기 이상인 경우, 이전 분기 데이터 조회하여 계산
                prev_quarter = data_quarter - 1
                prev_year = data_year
                prev_year_month = prev_year * 100 + prev_quarter * 3
                
                # 이전 분기 데이터 조회 (테이블에 따라 다른 메서드 사용)
                prev_data = await self._get_previous_quarter_data_by_type(
                    company_id, item_id, prev_year_month, statement_type
                )
                
                if prev_data:
                    logger.info(f"이전 분기 데이터 발견: {category}, {prev_year_month}, 값={prev_data.cumulative_value}")
                    # 해당 분기의 값 = 현재 누적값 - 이전 분기 누적값
                    period_value = value - prev_data.cumulative_value
                else:
                    logger.info(f"이전 분기 데이터 없음: {category}, {prev_year_month}")
                    # 이전 분기 데이터가 없으면 현재 값 그대로 사용
                    period_value = value
        
        return cumulative_value, period_value
        
    async def _save_to_appropriate_table(self, report_id, company_id, item_id, year_month, 
                                       value, unit, cumulative_value, period_value, 
                                       is_cumulative, statement_type, category, item_name) -> Any:
        """
        적절한 테이블에 데이터 저장
        
        Args:
            report_id: 보고서 ID
            company_id: 회사 ID
            item_id: 항목 ID
            year_month: 연월
            value: 값
            unit: 단위
            cumulative_value: 누적값
            period_value: 기간값
            is_cumulative: 누적 여부
            statement_type: 재무제표 유형
            category: 카테고리
            item_name: 항목명
            
        Returns:
            저장된 데이터 객체
        """
        repo = await self.repository
        
        # 재무제표 유형에 따라 적절한 테이블에 저장
        if "재무상태표" in category:
            # 재무상태표 테이블에 저장
            financial_data = await repo.save_balance_sheet_data(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative,
            )
            logger.info(f"재무상태표 항목 저장: {item_name}, 값={value} {unit}")
            
        elif "손익계산서" in category:
            # 손익계산서 테이블에 저장
            financial_data = await repo.save_income_statement_data(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative,
                statement_type=statement_type
            )
            logger.info(f"손익계산서 항목 저장: {item_name}, 값={value} {unit}")
            
        elif "포괄손익계산서" in category:
            # 포괄손익계산서 테이블에 저장 (손익계산서 테이블과 동일)
            financial_data = await repo.save_income_statement_data(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative,
                statement_type=statement_type
            )
            logger.info(f"포괄손익계산서 항목 저장: {item_name}, 값={value} {unit}")
            
        elif "현금흐름표" in category:
            # 현금흐름표 테이블에 저장
            financial_data = await repo.save_cash_flow_data(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative,
            )
            logger.info(f"현금흐름표 항목 저장: {item_name}, 값={value} {unit}")
            
        elif "자본변동표" in category:
            # 자본변동표 테이블에 저장
            financial_data = await repo.save_equity_change_data(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative,
            )
            logger.info(f"자본변동표 항목 저장: {item_name}, 값={value} {unit}")
            
        else:
            # 요약재무정보 테이블에 저장 (기본값)
            financial_data = await repo.save_summary_financial_data(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative,
                statement_type=statement_type
            )
            logger.info(f"요약재무정보 항목 저장: {item_name}, 값={value} {unit}")
        
        return financial_data
        
    async def _get_previous_quarter_data_by_type(
        self, company_id: int, item_id: int, year_month: int, statement_type: str
    ) -> Optional[Any]:
        """
        재무제표 유형에 따라 이전 분기 데이터 조회
        
        Args:
            company_id: 회사 ID
            item_id: 항목 ID
            year_month: 연월 (YYYYMM 형식)
            statement_type: 재무제표 유형
            
        Returns:
            이전 분기 데이터 또는 None
        """
        # 재무제표 유형에 따라 적절한 메서드 호출
        if statement_type == "balance_sheet":
            return await self._get_previous_quarter_balance_sheet_data(company_id, item_id, year_month)
        elif statement_type in ["income_statement", "comprehensive_income"]:
            return await self._get_previous_quarter_income_statement_data(company_id, item_id, year_month)
        elif statement_type == "cash_flow":
            return await self._get_previous_quarter_cash_flow_data(company_id, item_id, year_month)
        elif statement_type == "equity_change":
            return await self._get_previous_quarter_equity_change_data(company_id, item_id, year_month)
        else:
            # 기본값은 요약재무정보 테이블 사용
            return await self._get_previous_quarter_data(company_id, item_id, year_month)
        
    async def _get_previous_quarter_income_statement_data(
        self, company_id: int, item_id: int, year_month: int
    ) -> Optional[IncomeStatementData]:
        """
        이전 분기 손익계산서 데이터 조회
        
        Args:
            company_id: 회사 ID
            item_id: 항목 ID
            year_month: 연월 (YYYYMM 형식)
            
        Returns:
            이전 분기 데이터 또는 None
        """
        result = await self._db.execute(
            select(IncomeStatementData).where(
                and_(
                    IncomeStatementData.company_id == company_id,
                    IncomeStatementData.item_id == item_id,
                    IncomeStatementData.year_month == year_month
                )
            )
        )
        return result.scalar_one_or_none()
        
    async def _get_previous_quarter_data(
        self, company_id: int, item_id: int, year_month: int
    ) -> Optional[SummaryFinancialData]:
        """
        이전 분기 요약재무정보 데이터 조회
        
        Args:
            company_id: 회사 ID
            item_id: 항목 ID
            year_month: 연월 (YYYYMM 형식)
            
        Returns:
            이전 분기 데이터 또는 None
        """
        result = await self._db.execute(
            select(SummaryFinancialData).where(
                and_(
                    SummaryFinancialData.company_id == company_id,
                    SummaryFinancialData.item_id == item_id,
                    SummaryFinancialData.year_month == year_month
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_previous_quarter_balance_sheet_data(
        self, company_id: int, item_id: int, year_month: int
    ) -> Optional[BalanceSheetData]:
        """
        이전 분기 재무상태표 데이터 조회
        
        Args:
            company_id: 회사 ID
            item_id: 항목 ID
            year_month: 연월 (YYYYMM 형식)
            
        Returns:
            이전 분기 데이터 또는 None
        """
        result = await self._db.execute(
            select(BalanceSheetData).where(
                and_(
                    BalanceSheetData.company_id == company_id,
                    BalanceSheetData.item_id == item_id,
                    BalanceSheetData.year_month == year_month
                )
            )
        )
        return result.scalar_one_or_none()
        
    async def _get_previous_quarter_cash_flow_data(
        self, company_id: int, item_id: int, year_month: int
    ) -> Optional[CashFlowData]:
        """
        이전 분기 현금흐름표 데이터 조회
        
        Args:
            company_id: 회사 ID
            item_id: 항목 ID
            year_month: 연월 (YYYYMM 형식)
            
        Returns:
            이전 분기 데이터 또는 None
        """
        result = await self._db.execute(
            select(CashFlowData).where(
                and_(
                    CashFlowData.company_id == company_id,
                    CashFlowData.item_id == item_id,
                    CashFlowData.year_month == year_month
                )
            )
        )
        return result.scalar_one_or_none()
        
    async def _get_previous_quarter_equity_change_data(
        self, company_id: int, item_id: int, year_month: int
    ) -> Optional[EquityChangeData]:
        """
        이전 분기 자본변동표 데이터 조회
        
        Args:
            company_id: 회사 ID
            item_id: 항목 ID
            year_month: 연월 (YYYYMM 형식)
            
        Returns:
            이전 분기 데이터 또는 None
        """
        result = await self._db.execute(
            select(EquityChangeData).where(
                and_(
                    EquityChangeData.company_id == company_id,
                    EquityChangeData.item_id == item_id,
                    EquityChangeData.year_month == year_month
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_summary_financial_data(
        self, company_code: Optional[str] = None, 
        item_codes: Optional[List[str]] = None,
        start_year_month: Optional[int] = None,
        end_year_month: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        요약재무정보 조회
        
        Args:
            company_code: 회사 코드 (선택)
            item_codes: 항목 코드 목록 (선택)
            start_year_month: 시작 연월 (선택)
            end_year_month: 종료 연월 (선택)
            limit: 최대 조회 개수
            offset: 조회 시작 위치
            
        Returns:
            요약재무정보 목록
        """
        try:
            # 캐시 키 생성
            cache_key = self.cache_util.get_financial_cache_key(
                company_code, item_codes, start_year_month, end_year_month
            )
            
            # 캐시에서 조회
            cached_data = await self.cache_util.get_cache(cache_key)
            if cached_data:
                # 페이지네이션 처리
                total = cached_data.get("total", 0)
                items = cached_data.get("items", [])
                paginated_items = items[offset:offset+limit] if offset < len(items) else []
                
                return {
                    "success": True,
                    "total": total,
                    "items": paginated_items,
                    "from_cache": True
                }
            
            # 저장소에서 조회
            repo = await self.repository
            data, total = await repo.get_summary_financial_data(
                company_code=company_code,
                item_codes=item_codes,
                start_year_month=start_year_month,
                end_year_month=end_year_month,
                limit=limit,
                offset=offset
            )
            
            result = {
                "success": True,
                "total": total,
                "items": data,
                "from_cache": False
            }
            
            # 결과 캐싱 (전체 데이터)
            if total <= 1000:  # 데이터가 많지 않은 경우에만 캐싱
                all_data, _ = await repo.get_summary_financial_data(
                    company_code=company_code,
                    item_codes=item_codes,
                    start_year_month=start_year_month,
                    end_year_month=end_year_month,
                    limit=total,
                    offset=0
                )
                
                cache_data = {
                    "success": True,
                    "total": total,
                    "items": all_data
                }
                
                await self.cache_util.set_cache(cache_key, cache_data)
            
            return result
            
        except Exception as e:
            logger.error(f"요약재무정보 조회 중 오류 발생: {e}")
            return {
                "success": False,
                "message": f"요약재무정보 조회 중 오류 발생: {str(e)}"
            }
    
    async def get_company_financial_summary(
        self, company_code: str, 
        item_codes: Optional[List[str]] = None,
        latest_only: bool = False
    ) -> Dict[str, Any]:
        """
        회사별 요약재무정보 조회
        
        Args:
            company_code: 회사 코드
            item_codes: 항목 코드 목록 (선택)
            latest_only: 최신 데이터만 조회 여부
            
        Returns:
            회사별 요약재무정보
        """
        try:
            # 회사 정보 조회
            repo = await self.repository
            company = await repo.get_company_by_code(company_code)
            
            if not company:
                return {
                    "success": False,
                    "message": f"회사 정보가 없습니다: {company_code}"
                }
            
            # 재무 데이터 조회
            data, total = await repo.get_summary_financial_data(
                company_code=company_code,
                item_codes=item_codes,
                limit=1000 if not latest_only else 100
            )
            
            # 데이터 구조화
            financial_data = {}
            
            for item in data:
                item_code = item["item_code"]
                if item_code not in financial_data:
                    financial_data[item_code] = {
                        "item_code": item_code,
                        "item_name": item["item_name"],
                        "values": []
                    }
                
                financial_data[item_code]["values"].append({
                    "year_month": item["year_month"],
                    "value": item["value"],
                    "display_unit": item["display_unit"]
                })
            
            if latest_only:
                # 각 항목별로 최신 데이터만 남기기
                for item_code in financial_data:
                    financial_data[item_code]["values"] = sorted(
                        financial_data[item_code]["values"],
                        key=lambda x: x["year_month"],
                        reverse=True
                    )[:1]
            
            return {
                "success": True,
                "company_code": company_code,
                "company_name": company.company_name,
                "data": list(financial_data.values())
            }
            
        except Exception as e:
            logger.error(f"회사별 요약재무정보 조회 중 오류 발생: {e}")
            return {
                "success": False,
                "message": f"회사별 요약재무정보 조회 중 오류 발생: {str(e)}"
            }

