"""
재무 데이터 서비스 클래스

이 모듈은 종목 코드에 대한 재무 데이터를 조회하고 처리하기 위한 서비스를 제공합니다.
GCS에서 PDF 파일을 관리하고 처리하는 로직을 포함합니다.
"""

import os
import json
import asyncio
import logging
import warnings
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, List, Any, Optional, Tuple
import re
from pathlib import Path

from google.cloud import storage
from common.services.storage import GoogleCloudStorageService
from common.core.config import settings

import fitz  # PyMuPDF 라이브러리
import pdfplumber  # pdfplumber 추가

# PDF 관련 모든 경고 메시지 숨기기
warnings.filterwarnings('ignore', category=UserWarning, module='pdfminer')
warnings.filterwarnings('ignore', category=UserWarning, module='pdfplumber')

logger = logging.getLogger(__name__)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

class FinancialDataService:
    """재무 데이터 서비스 클래스"""
    
    def __init__(self):
        """서비스 초기화"""
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
    

