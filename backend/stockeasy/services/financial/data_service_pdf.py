"""
재무 데이터 서비스 클래스

이 모듈은 종목 코드에 대한 재무 데이터를 조회하고 처리하기 위한 서비스를 제공합니다.
GCS에서 PDF 파일을 관리하고 처리하는 로직을 포함합니다.
"""

import os
import json
import asyncio
from loguru import logger
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

# PyMuPDF 디버그 출력 비활성화
fitz.TOOLS.mupdf_display_errors = False

# PDF 관련 모든 경고 메시지 숨기기
warnings.filterwarnings('ignore', category=UserWarning, module='pdfminer')
warnings.filterwarnings('ignore', category=UserWarning, module='pdfplumber')
warnings.filterwarnings('ignore', category=UserWarning, module='fitz')  # PyMuPDF 경고 숨기기
warnings.filterwarnings('ignore', message='CropBox missing from /Page, defaulting to MediaBox')
import logging
# # 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력용 핸들러
    ]
)
logger2 = logging.getLogger(__name__)
logger2.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정
logging.getLogger("pdfminer").setLevel(logging.ERROR)

class FinancialDataServicePDF:
    """재무 데이터 서비스 클래스"""
    
    def __init__(self, db_session: AsyncSession = None):
        """서비스 초기화"""
        self._db = db_session
        
        # 로거 초기화 메시지 출력
        logger.info("FinancialDataServicePDF 초기화 중...")
        
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
        #self.cache_util = FinancialCacheUtil()
        
        logger.info("FinancialDataServicePDF 초기화 완료")
        
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
                    #print(f"append file_date: {file_date}")
                    filtered_files.append(file)
                # elif file.get("year", 0) >= start_date.year and file.get("year", 0) <= end_date.year:
                #     print(f"append file_date2: {file_date}")
                #     filtered_files.append(file)
            
            if not filtered_files:
                logger.warning(f"지정 기간 내 재무 보고서가 없습니다: {stock_code}, 기간: {start_date} ~ {end_date}")
                return {}
                
            # 로그는 한글로 작성
            print(f"조회 기간 내 재무 보고서 {len(filtered_files)}개 찾았습니다: {stock_code}")
            
            # 3. 각 파일에서 데이터 추출 (병렬 처리)
            logger.info(f"[성능개선] {len(filtered_files)}개 파일에서 데이터 추출 병렬 처리 시작")
            parallel_start_time = datetime.now()
            
            # 파일별 처리 함수 정의
            async def process_file(file_info):
                try:
                    file_path = file_info.get("file_path")
                    local_path = await self._ensure_local_file(file_path)
                    
                    if local_path:
                        # 페이지 추출 및 데이터 추가
                        financial_statement_pages = await self._extract_financial_statement_pages(local_path)
                        if financial_statement_pages:
                            report_type = file_info.get("type", "unknown")
                            report_year = file_info.get("year", 0)
                            
                            # 데이터 구조화
                            return (f"{report_year}_{report_type}", {
                                "content": financial_statement_pages,
                                "metadata": {
                                    "year": report_year,
                                    "type": report_type,
                                    "file_name": os.path.basename(file_path),
                                    "date": file_info.get("date", "")
                                }
                            })
                    return None
                except Exception as e:
                    logger.error(f"파일 처리 중 오류: {file_info.get('file_path', '')}, 오류: {str(e)}")
                    return None
            
            # 모든 파일을 병렬로 처리
            results = await asyncio.gather(
                *[process_file(file_info) for file_info in filtered_files],
                return_exceptions=True
            )
            
            # 결과 수집
            financial_data = {}
            successful_count = 0
            for result in results:
                if isinstance(result, tuple) and result is not None:
                    key, data = result
                    financial_data[key] = data
                    successful_count += 1
                elif isinstance(result, Exception):
                    logger.error(f"파일 처리 중 예외 발생: {str(result)}")
            
            parallel_duration = (datetime.now() - parallel_start_time).total_seconds()
            logger.info(f"[성능개선] 파일 병렬 처리 완료 - {successful_count}/{len(filtered_files)}개 성공, 소요시간: {parallel_duration:.2f}초")
            
            # 4. 데이터를 시간 순으로 정렬하여 반환
            sorted_data = dict(sorted(
                financial_data.items(),
                key=lambda x: (x[1]["metadata"]["year"], x[1]["metadata"]["type"]),
                reverse=True  # 최신 데이터 우선
            ))
            
            return {
                "stock_code": stock_code,
                "count": len(sorted_data),
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
                    filtered_files.append(file)
            
            if not filtered_files:
                logger.warning(f"지정 기간 내 재무 보고서가 없습니다: {stock_code}, 기간: {start_date} ~ {end_date}")
                return {}
                
            # 로그는 한글로 작성
            print(f"조회 기간 내 재무 보고서 {len(filtered_files)}개 찾았습니다: {stock_code}")
            
            # 3. 각 파일에서 데이터 추출 (병렬 처리)
            logger.info(f"[성능개선] {len(filtered_files)}개 파일에서 매출 분석 데이터 추출 병렬 처리 시작")
            parallel_start_time = datetime.now()
            
            # 파일별 처리 함수 정의
            async def process_revenue_file(file_info):
                try:
                    file_path = file_info.get("file_path")
                    local_path = await self._ensure_local_file(file_path)
                    
                    if local_path:
                        # 페이지 추출 및 데이터 추가
                        business_report_info = await self.extract_business_report_info(local_path)
                        extracted_data = await self.extract_revenue_breakdown_data(local_path, business_report_info)
                        if extracted_data:  # None이나 빈 문자열이 아닌 경우에만 추가
                            return extracted_data
                    return ""
                except Exception as e:
                    logger.error(f"매출 데이터 파일 처리 중 오류: {file_info.get('file_path', '')}, 오류: {str(e)}")
                    return ""
            
            # 모든 파일을 병렬로 처리
            results = await asyncio.gather(
                *[process_revenue_file(file_info) for file_info in filtered_files],
                return_exceptions=True
            )
            
            # 결과 수집
            revenue_breakdown_data = ""
            successful_count = 0
            for result in results:
                if isinstance(result, str) and result:
                    revenue_breakdown_data += result
                    successful_count += 1
                elif isinstance(result, Exception):
                    logger.error(f"매출 데이터 파일 처리 중 예외 발생: {str(result)}")
            
            parallel_duration = (datetime.now() - parallel_start_time).total_seconds()
            logger.info(f"[성능개선] 매출 데이터 파일 병렬 처리 완료 - {successful_count}/{len(filtered_files)}개 성공, 소요시간: {parallel_duration:.2f}초")

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
        #blobs = list(self.storage_service.bucket.list_blobs(prefix=prefix))
        blobs = await asyncio.to_thread(self.storage_service.bucket.list_blobs, prefix=prefix)
        
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
                # 삽질.
                # if report_type.lower() == "annual":
                #     year = date.year -1
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
            fs_pages = []
            keywords = ["연결재무상태표", 
                       "연결현금흐름표", "재무상태표",
                       "재무에 관한 사항", "연결재무제표", "요약재무정보"]
            
            # 1. fitz로 목차 페이지 찾기
            doc = await asyncio.to_thread(fitz.open, pdf_path)
            target_pages = set()
            
            try:
                # 목차 정보 가져오기
                toc = await asyncio.to_thread(doc.get_toc)
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
                
                # 목차에서 페이지를 찾지 못한 경우 키워드로 검색
                if not target_pages:
                    logger.info("No pages found in TOC, searching by keywords...")
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        text = await asyncio.to_thread(page.get_text)
                        if any(keyword in text for keyword in keywords):
                            # 키워드가 발견된 페이지와 뒤따르는 2페이지 추가
                            for i in range(3):  # 현재 페이지 포함 3페이지
                                check_page = page_num + i
                                if 0 <= check_page < len(doc):
                                    target_pages.add(check_page)
            
            finally:
                await asyncio.to_thread(doc.close)
            
            # 2. pdfplumber로 찾은 페이지의 내용 추출
            if target_pages:
                # pdfplumber를 비동기 방식으로 사용
                async def extract_with_pdfplumber():
                    nonlocal fs_pages
                    with pdfplumber.open(pdf_path) as pdf:
                        for page_num in sorted(target_pages):
                            if page_num < len(pdf.pages):
                                page = pdf.pages[page_num]
                                text = await asyncio.to_thread(page.extract_text)
                                if text and text.strip():  # 빈 페이지가 아닌 경우만 추가
                                    fs_pages.append((page_num, text))
                
                # 비동기 추출 실행
                await extract_with_pdfplumber()
                
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
        
    async def extract_revenue_breakdown_data(self, target_report: str, business_report_info: Dict[str, Any]):
        """
        주어진 사업보고서 파일에서 매출 및 수주 현황 정보를 추출합니다.
        
        Args:
            target_report: 사업보고서 파일 경로
            business_report_info: 사업보고서 정보
             Dict[str, Any]: 기수 및 사업년도 정보를 포함하는 딕셔너리
                - period_number: 기수 (int)
                - business_year_start: 사업년도 시작일 (str, 'YYYY-MM-DD' 형식)
                - business_year_end: 사업년도 종료일 (str, 'YYYY-MM-DD' 형식)
                - title: 보고서 제목 (str)
                - company_name: 회사명 (str)
        return :
            매출 및 수주상황 섹션 텍스트 
        """
        doc = None  # 함수 반환 시 닫아야 할 doc 객체를 위한 변수 선언
        try:
            base_file_name = os.path.basename(target_report)
            logger.info(f"매출 정보 추출 시작: {base_file_name}")
            
            year = base_file_name.split("_")[0][:4]
            quater_file = base_file_name.split("_")[4]
            
            report_type_map = {
                    "Q1": "1Q",
                    "Q3": "3Q",
                    "semiannual": "2Q",
                    "annual": "4Q"
                }
            
            quater = report_type_map.get(quater_file, "")
            #logger.info(f"보고서 기간: {year}.{quater}")

            # 3. fitz를 사용하여 목차 내용 추출
            doc = await asyncio.to_thread(fitz.open, target_report)
            toc = await asyncio.to_thread(doc.get_toc)  # 목차 가져오기 비동기로 처리
            #logger.info(f"목차 항목 수: {len(toc)}")
            
            if not toc:
                logger.error("목차를 찾을 수 없습니다.")
                return ""
            
            # 4. 목차에서 'II. 사업의 내용' 및 '매출 및 수주상황' 찾기
            business_content_start_page = None
            business_content_end_page = None
            sales_section_start_page = None
            sales_section_end_page = None
            
            # 페이지 범위 정보 디버깅을 위한 함수
            # def log_page_info(prefix, page_var, page_num):
            #     if page_var is not None:
            #         logger.info(f"{prefix} {page_var}(값: {page_num})")
            #     else:
            #         logger.info(f"{prefix} 없음")
            
            for i, item in enumerate(toc):
                level, title, page_num = item
                #logger.debug(f"목차 항목: {level} - {title} - {page_num}")
                
                # 'II. 사업의 내용' 목차 찾기
                if "사업의 내용" in title and (title.startswith("II.") or title.startswith("Ⅱ.")):
                    business_content_start_page = page_num - 1  # 0-based 페이지 번호로 변환
                    #logger.info(f"'사업의 내용' 섹션 시작: 페이지 {business_content_start_page+1}")
                    
                    # 다음 대분류 목차를 찾아 끝 페이지 결정
                    for next_item in toc[i+1:]:
                        next_level, next_title, next_page = next_item
                        if next_level <= level and (next_title.startswith("III.") or next_title.startswith("Ⅲ.") or 
                                                next_title.startswith("IV.") or next_title.startswith("Ⅳ.")):
                            business_content_end_page = next_page - 2  # 다음 대분류 시작 전 페이지
                            #logger.info(f"'사업의 내용' 섹션 종료: 페이지 {business_content_end_page+1}")
                            break
                    
                    # 다음 대분류가 없으면 문서 끝까지를 범위로 설정
                    if business_content_end_page is None:
                        business_content_end_page = len(doc) - 1
                        #logger.info(f"'사업의 내용' 섹션 종료(문서 끝): 페이지 {business_content_end_page+1}")
                
                # '매출 및 수주상황' 목차 찾기 (II. 사업의 내용 아래에 있어야 함)
                if business_content_start_page is not None and "매출" in title and "수주" in title:
                    sales_section_start_page = page_num - 1  # 0-based 페이지 번호로 변환
                    #logger.info(f"'매출 및 수주상황' 섹션 시작: 페이지 {sales_section_start_page+1}")
                    
                    # 다음 동일 레벨 또는 상위 레벨 목차를 찾아 끝 페이지 결정
                    for next_item in toc[i+1:]:
                        next_level, next_title, next_page = next_item
                        if next_level <= level:
                            sales_section_end_page = next_page - 2  # 다음 섹션 시작 전 페이지
                            #logger.info(f"'매출 및 수주상황' 섹션 종료: 페이지 {sales_section_end_page+1}")
                            break
                    
                    # 다음 섹션이 없으면 사업의 내용 끝까지를 범위로 설정
                    if sales_section_end_page is None and business_content_end_page is not None:
                        sales_section_end_page = business_content_end_page
                        #logger.info(f"'매출 및 수주상황' 섹션 종료(사업의 내용 끝): 페이지 {sales_section_end_page+1}")
                    
                    break  # 매출 및 수주상황 섹션을 찾았으므로 검색 종료
            
            # 5. 페이지 범위 결정 (매출 및 수주상황을 찾지 못했다면 사업의 내용 전체를 사용)
            start_page = None
            end_page = None
            
            # 각 값의 상태 기록
            # log_page_info("sales_section_start_page:", "변수", sales_section_start_page)
            # log_page_info("sales_section_end_page:", "변수", sales_section_end_page)
            # log_page_info("business_content_start_page:", "변수", business_content_start_page)
            # log_page_info("business_content_end_page:", "변수", business_content_end_page)
            
            if sales_section_start_page is not None and sales_section_end_page is not None:
                start_page = sales_section_start_page
                end_page = sales_section_end_page
                logger.info(f"'매출 및 수주상황' 섹션을 찾았습니다: 페이지 {start_page+1}~{end_page+1}")
            elif business_content_start_page is not None and business_content_end_page is not None:
                start_page = business_content_start_page
                end_page = business_content_end_page
                logger.info(f"'II. 사업의 내용' 섹션을 찾았습니다: 페이지 {start_page+1}~{end_page+1}")
            else:
                logger.error("매출 및 수주상황, 사업의 내용 섹션을 찾을 수 없습니다.")
                return ""
            
            # 추가 검증
            if start_page is None or end_page is None:
                logger.error(f"페이지 범위가 제대로 설정되지 않았습니다: start_page={start_page}, end_page={end_page}")
                return ""
                
            if end_page < start_page:
                logger.error(f"페이지 범위가 잘못되었습니다: start_page={start_page}, end_page={end_page}")
                # 안전 처리: end_page가 start_page보다 작으면 end_page를 start_page로 설정
                end_page = start_page
            
            # 6. pdfplumber를 사용하여 해당 페이지 내용 추출
            extracted_text = f"-----------------------------\n\n"
            extracted_text += f"<{year}.{quater} 데이터>\n\n"
            extracted_text += f"<기수>제 {business_report_info.get('period_number')}기</기수>\n"
            extracted_text += f"<사업년도>{business_report_info.get('business_year_start')} ~ {business_report_info.get('business_year_end')}</사업년도>\n"
            
            # pdfplumber 사용 (try/except 블록 적용)
            try:
                #logger.info(f"PDF 페이지 추출 시작: {start_page+1}~{end_page+1}")
                
                with pdfplumber.open(target_report) as pdf:
                    # 페이지 범위가 너무 크면 최대 페이지로 제한
                    max_pages = 30
                    pdf_length = len(pdf.pages)
                    #logger.info(f"PDF 총 페이지 수: {pdf_length}")
                    
                    # 페이지 범위 유효성 검사 및 조정
                    if start_page >= pdf_length:
                        logger.warning(f"시작 페이지({start_page+1})가 PDF 길이({pdf_length})를 초과합니다")
                        start_page = max(0, pdf_length - 1)
                    
                    if end_page >= pdf_length:
                        logger.warning(f"종료 페이지({end_page+1})가 PDF 길이({pdf_length})를 초과합니다")
                        end_page = pdf_length - 1
                    
                    # 범위가 너무 넓으면 제한
                    effective_end_page = end_page
                    if end_page - start_page > max_pages:
                        logger.warning(f"페이지 범위가 너무 큽니다({start_page+1}~{end_page+1}). 처음 {max_pages}페이지만 추출합니다.")
                        effective_end_page = start_page + max_pages
                    
                    logger.info(f"최종 추출 페이지 범위: {start_page+1}~{effective_end_page+1}")
                    
                    # 페이지 추출
                    for page_num in range(start_page, effective_end_page + 1):
                        try:
                            page = pdf.pages[page_num]
                            text = page.extract_text()  # 동기 처리 (더 안정적)
                            if text:
                                extracted_text += f"\n\n<Page.{page_num + 1}>\n\n{text}\n</Page.{page_num + 1}>"
                                logger.debug(f"페이지 {page_num+1} 추출 완료: {len(text)} 글자")
                        except Exception as page_error:
                            logger.error(f"페이지 {page_num+1} 추출 오류: {str(page_error)}")
            
            except Exception as pdf_error:
                logger.exception(f"PDF 처리 중 오류: {str(pdf_error)}")
                # 오류가 발생했더라도, 지금까지 추출한 내용은 반환
            
            extracted_text += f"\n\n</{year}.{quater} 데이터>\n"
            
            # 추출된 결과 확인
            if not extracted_text or extracted_text.count("<Page.") == 0:
                logger.error("추출된 텍스트가 없습니다.")
                return ""
                
            logger.info(f"텍스트 추출 완료: {len(extracted_text)} 글자, {extracted_text.count('<Page.')} 페이지")
            return extracted_text
            
        except Exception as e:
            logger.exception(f"Error extracting revenue breakdown data: {str(e)}")
            return ""
            
        finally:
            # 리소스 정리
            if doc is not None:
                try:
                    doc.close()
                    logger.debug("PDF 문서 리소스 해제 완료")
                except Exception as close_error:
                    logger.error(f"PDF 문서 리소스 해제 오류: {str(close_error)}")
    
    async def extract_business_report_info(self, target_report: str) -> Dict[str, Any]:
        """
        사업보고서의 초반부 페이지를 읽어서 기수 및 사업년도 정보를 추출합니다.
        
        Args:
            target_report: 사업보고서 파일 경로
            
        Returns:
            Dict[str, Any]: 기수 및 사업년도 정보를 포함하는 딕셔너리
                - period_number: 기수 (int)
                - business_year_start: 사업년도 시작일 (str, 'YYYY-MM-DD' 형식)
                - business_year_end: 사업년도 종료일 (str, 'YYYY-MM-DD' 형식)
                - title: 보고서 제목 (str)
                - company_name: 회사명 (str)
        """
        try:
            logger.info(f"사업보고서 정보 추출 시작: {target_report}")
            
            # 기본 결과 구조 초기화
            result = {
                "period_number": None,  # 기수
                "business_year_start": None,  # 사업년도 시작일
                "business_year_end": None,  # 사업년도 종료일
                "title": None,  # 보고서 제목
                "company_name": None  # 회사명
            }
            
            # 파일명에서 기본 정보 추출
            base_file_name = os.path.basename(target_report)
            file_info = self._parse_filename(base_file_name)
            if file_info:
                result["company_name"] = file_info.get("company")
            
            # PDF 파일 열기
            doc = await asyncio.to_thread(fitz.open, target_report)
            
            try:
                # 처음 10페이지만 검사 (표지와 초반 정보 페이지)
                max_pages = min(10, len(doc))
                
                # 정규식 패턴 준비
                period_pattern = re.compile(r"제\s*(\d+)\s*기")  # 제 00 기
                business_year_pattern = re.compile(r"사업(연도|년도)\s*:\s*(\d{4}[.\-/년]?\s*\d{1,2}[.\-/월]?\s*\d{1,2}[일]?)(?:\s*~\s*|\s*부터\s*|\s*에서\s*)(\d{4}[.\-/년]?\s*\d{1,2}[.\-/월]?\s*\d{1,2}[일]?)")
                
                # 여러 줄에 걸친 사업연도 패턴 (사업연도, 날짜, 부터, 날짜, 까지 형식)
                multiline_year_pattern = re.compile(r"사업(?:연도|년도)\s*(?:[:：]?\s*)?$", re.MULTILINE)
                date_pattern = re.compile(r"(\d{4}[.\-/년]?\s*\d{1,2}[.\-/월]?\s*\d{1,2}[일]?)")
                from_to_pattern = re.compile(r"부터|까지", re.MULTILINE)
                
                for page_num in range(max_pages):
                    page = doc[page_num]
                    # fitz의 get_text 메서드를 비동기적으로 실행
                    text = await asyncio.to_thread(page.get_text)
                    
                    # 기수 찾기
                    if result["period_number"] is None:
                        period_match = period_pattern.search(text)
                        if period_match:
                            result["period_number"] = int(period_match.group(1))
                            logger.info(f"기수 정보 발견: 제 {result['period_number']} 기")
                            #logger.info(f"{text}")
                    
                    # 사업년도 찾기 (한 줄 패턴)
                    if result["business_year_start"] is None or result["business_year_end"] is None:
                        business_year_match = business_year_pattern.search(text)
                        if business_year_match:
                            # 날짜 형식 정규화
                            start_date = self._normalize_date(business_year_match.group(2))
                            end_date = self._normalize_date(business_year_match.group(3))
                            
                            result["business_year_start"] = start_date
                            result["business_year_end"] = end_date
                            logger.info(f"사업년도 정보 발견: {start_date} ~ {end_date}")
                    
                    # 여러 줄에 걸친 사업년도 패턴 찾기
                    if (result["business_year_start"] is None or result["business_year_end"] is None) and "사업연도" in text:
                        # '사업연도' 문자열이 있는지 확인
                        multiline_matches = list(multiline_year_pattern.finditer(text))
                        if multiline_matches:
                            # '사업연도' 이후의 텍스트에서 날짜와 '부터', '까지' 찾기
                            year_index = multiline_matches[0].start()
                            remaining_text = text[year_index:]
                            
                            # 날짜 찾기
                            date_matches = list(date_pattern.finditer(remaining_text))
                            from_to_matches = list(from_to_pattern.finditer(remaining_text))
                            
                            # 날짜가 두 개 이상이고 '부터'/'까지' 키워드가 있으면 처리
                            if len(date_matches) >= 2 and len(from_to_matches) >= 1:
                                # 첫 번째와 두 번째 날짜 추출
                                start_date_str = date_matches[0].group(1)
                                end_date_str = date_matches[1].group(1)
                                
                                # 날짜 형식 정규화
                                start_date = self._normalize_date(start_date_str)
                                end_date = self._normalize_date(end_date_str)
                                
                                result["business_year_start"] = start_date
                                result["business_year_end"] = end_date
                                logger.info(f"여러 줄 사업년도 정보 발견: {start_date} ~ {end_date}")
                                #logger.info(f"원본 텍스트:\n{remaining_text[:200]}...")
                    
                    # 보고서 제목 찾기 (보통 첫 페이지에 있음)
                    if page_num == 0 and result["title"] is None:
                        # 페이지에서 큰 글꼴의 텍스트 블록 추출 (비동기로 처리)
                        page_dict = await asyncio.to_thread(page.get_text, "dict")
                        blocks = page_dict["blocks"]
                        for block in blocks:
                            if "lines" in block:
                                for line in block["lines"]:
                                    if "spans" in line:
                                        for span in line["spans"]:
                                            # 글꼴 크기가 크고 "보고서" 단어가 포함된 텍스트를 제목으로 간주
                                            if span.get("size", 0) > 14 and "보고서" in span.get("text", ""):
                                                result["title"] = span.get("text").strip()
                                                break
                
                # 결과 로깅
                logger.info(f"사업보고서 정보 추출 결과: {result}")
                return result
                
            finally:
                doc.close()
                
        except Exception as e:
            logger.exception(f"사업보고서 정보 추출 중 오류 발생: {str(e)}")
            return {
                "period_number": None,
                "business_year_start": None,
                "business_year_end": None,
                "title": None,
                "company_name": None,
                "error": str(e)
            }
    
    def _normalize_date(self, date_str: str) -> str:
        """
        다양한 형식의 날짜 문자열을 YYYY-MM-DD 형식으로 정규화합니다.
        
        Args:
            date_str: 정규화할 날짜 문자열
            
        Returns:
            정규화된 날짜 문자열 (YYYY-MM-DD 형식)
        """
        try:
            # 입력 문자열 정리
            date_str = date_str.strip()
            #logger.debug(f"날짜 정규화 시작: '{date_str}'")
            
            # 특수문자 및 한글 제거
            date_str = re.sub(r'[년월일\s]', '.', date_str)
            date_str = re.sub(r'[^\d.]', '', date_str)
            
            # 구분자 통일
            date_str = date_str.replace('/', '.').replace('-', '.')
            
            # 연속된 구분자 제거
            while '..' in date_str:
                date_str = date_str.replace('..', '.')
            
            # 앞뒤 점 제거
            date_str = date_str.strip('.')
            
            # 구분자로 분리
            parts = date_str.split('.')
            
            # 년-월-일 형식 확인 및 보정
            if len(parts) >= 3:
                year = parts[0].zfill(4)
                month = parts[1].zfill(2)
                day = parts[2].zfill(2)
                
                # 년도가 2자리인 경우 20xx로 가정
                if len(year) == 2:
                    year = "20" + year
                
                # 간단한 유효성 검사
                year_int = int(year)
                month_int = int(month)
                day_int = int(day)
                
                # 유효한 범위인지 확인
                if 1900 <= year_int <= 2100 and 1 <= month_int <= 12 and 1 <= day_int <= 31:
                    # 월에 따른 일자 유효성 확인
                    days_in_month = {
                        1: 31, 2: 29 if (year_int % 4 == 0 and year_int % 100 != 0) or year_int % 400 == 0 else 28,
                        3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
                    }
                    
                    if day_int <= days_in_month[month_int]:
                        return f"{year}-{month}-{day}"
                    else:
                        logger.warning(f"유효하지 않은 날짜: {year}-{month}-{day} (일자가 해당 월의 최대 일수를 초과)")
                else:
                    logger.warning(f"유효하지 않은 날짜 범위: {year}-{month}-{day}")
            
            # 부분적인 정보만 있는 경우 (년도와 월만 있는 경우)
            if len(parts) == 2:
                year = parts[0].zfill(4)
                month = parts[1].zfill(2)
                
                # 년도가 2자리인 경우 20xx로 가정
                if len(year) == 2:
                    year = "20" + year
                    
                # 간단한 유효성 검사
                if 1900 <= int(year) <= 2100 and 1 <= int(month) <= 12:
                    return f"{year}-{month}-01"  # 해당 월의 1일로 가정
            
            # 형식이 맞지 않으면 원본에서 숫자만 추출해서 처리 시도
            digits = re.findall(r'\d+', date_str)
            if len(digits) >= 3:
                year = digits[0].zfill(4)
                month = digits[1].zfill(2)
                day = digits[2].zfill(2)
                
                # 년도가 2자리인 경우 20xx로 가정
                if len(year) == 2:
                    year = "20" + year
                
                if len(year) == 4 and len(month) <= 2 and len(day) <= 2:
                    if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 형식이 맞지 않으면 원본 반환
            logger.warning(f"날짜 형식 정규화 실패: {date_str}")
            return date_str
            
        except Exception as e:
            logger.warning(f"날짜 정규화 중 오류: {str(e)}, 원본: {date_str}")
            return date_str
    