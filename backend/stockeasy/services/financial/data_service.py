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
        
    async def get_financial_data(self, stock_code: str, year_range: int = 2) -> Dict[str, Any]:
        """
        주어진 종목 코드에 대한 재무 데이터를 가져옵니다.
        
        Args:
            stock_code: 종목 코드
            year_range: 최근 몇 년 동안의 데이터를 가져올지 (기본값: 2년)
            
        Returns:
            재무 데이터를 포함하는 딕셔너리
        """
        try:
            # 1. 파일 목록 가져오기
            file_list = await self._get_file_list(stock_code)
            
            # 2. 파일 목록 필터링 (연도 기준)
            now = datetime.now()
            start_year = now.year - year_range
            filtered_files = [
                file for file in file_list 
                if file.get("year", 0) >= start_year
            ]
            
            if not filtered_files:
                logger.warning(f"No financial reports found for stock {stock_code} in the last {year_range} years")
                return {}
                
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
                "reports": sorted_data
            }
            
        except Exception as e:
            logger.exception(f"Error getting financial data for stock {stock_code}: {str(e)}")
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
                logger.info(f"Using memory cached file list for stock {stock_code}")
                return cache_entry["data"]
        
        # 2. 파일 캐시 확인
        if await self._is_file_list_cache_valid():
            try:
                with open(self.file_list_cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    if stock_code in cached_data:
                        # 메모리 캐시 업데이트
                        self._file_list_cache[stock_code] = {
                            "data": cached_data[stock_code],
                            "timestamp": now
                        }
                        logger.info(f"Using file cached list for stock {stock_code}")
                        return cached_data[stock_code]
            except Exception as e:
                logger.warning(f"Failed to load cached file list: {str(e)}")
        
        # 3. GCS에서 파일 목록 가져오기
        logger.info(f"Retrieving file list from GCS for stock {stock_code}")
        
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
        
    async def _is_file_list_cache_valid(self) -> bool:
        """
        파일 목록 캐시가 유효한지 확인합니다.
        마지막 쓰기 시간을 메모리에 저장하여 파일 접근을 최소화합니다.
        
        Returns:
            캐시가 유효하면 True, 그렇지 않으면 False
        """
        if not os.path.exists(self.file_list_cache_path):
            return False
            
        now = datetime.now()
        
        # 마지막 쓰기 시간이 메모리에 있으면 그것을 사용
        if self._last_cache_write:
            return (now - self._last_cache_write).total_seconds() < self.cache_expiry
            
        # 파일 수정 시간 확인
        file_mtime = datetime.fromtimestamp(os.path.getmtime(self.file_list_cache_path))
        self._last_cache_write = file_mtime
        
        return (now - file_mtime).total_seconds() < self.cache_expiry
        
    async def _update_file_list_cache(self, stock_code: str, file_list: List[Dict[str, Any]]) -> None:
        """
        파일 목록 캐시를 업데이트합니다.
        
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
            
            # 새 데이터 추가/업데이트
            cached_data[stock_code] = file_list
            
            # 캐시 파일 저장
            with open(self.file_list_cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, ensure_ascii=False, indent=2)
            
            # 마지막 쓰기 시간 업데이트
            self._last_cache_write = datetime.now()
            
            logger.info(f"Updated file list cache for stock {stock_code}")
        except Exception as e:
            logger.warning(f"Failed to update file list cache: {str(e)}")
            
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
            keywords = ["연결재무상태표", "연결손익계산서", "연결포괄손익계산서", 
                      "연결현금흐름표", "재무상태표", "손익계산서", "포괄손익계산서",
                      "재무에 관한 사항", "연결재무제표", "요약재무정보"]
            
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