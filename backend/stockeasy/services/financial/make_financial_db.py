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
from stockeasy.utils.parsing_util import _process_numeric_value, remove_comment_number, remove_number_prefix_toc

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

# 목차 찾기 전용 키워드 목록 (찾고자 하는 재무제표 유형)
toc_income_statement_keywords = [
    "연결포괄손익계산서",
    "연결손익계산서", 
    "포괄손익계산서", 
    "반기포괄손익계산서",
    "분기포괄손익계산서",
    
    "요약반기연결포괄손익계산서",
    "요약분기연결포괄손익계산서",

    "요약분기포괄손익계산서",
    "요약반기포괄손익계산서",
    "분기연결포괄손익계산서",
    
    "반기연결포괄손익계산서",
    "손익계산서"
]
toc_cash_flow_keywords = [
    "연결현금흐름표",
    "별도현금흐름표",
    "요약분기연결현금흐름표",
    "분기연결현금흐름표",
    "요약반기연결현금흐름표",
    "반기연결현금흐름표",
    "요약분기현금흐름표",
    "요약반기현금흐름표",
    "현금흐름표"
]
toc_balance_sheet_keywords = [
    "연결재무상태표",
    "별도재무상태표",
    "요약분기연결재무상태표",
    "분기연결재무상태표",
    "요약반기연결재무상태표",
    "반기연결재무상태표",
    "요약분기자본변동표",
    "요약반기자본변동표"
    "재무상태표"
]
toc_capital_changes_keywords = [
    "연결자본변동표",
    "별도자본변동표",
    "요약분기연결자본변동표",
    "분기연결자본변동표",
    "요약반기연결자본변동표",
    "반기연결자본변동표",
    "요약분기자본변동표",
    "요약반기자본변동표",
    "자본변동표"
]

# 키워드 목록 (찾고자 하는 재무제표 유형)
income_statement_keywords = [
    "연결 포괄손익계산서", "연결포괄손익계산서", "연 결 포 괄 손 익 계 산 서",
    "연결 손익계산서", "연결손익계산서", 
    "포괄손익계산서", "손익계산서"
]
cash_flow_keywords = [
    "연결현금흐름표", "연결 현금흐름표", "연  결  현  금 흐 름 표",
    "별도 현금흐름표", "별도현금흐름표",
    "현금흐름표", "현 금 흐 름 표"
]
balance_sheet_keywords = [
    "연결재무상태표", "연결 재무상태표", "연 결 재 무 상 태 표",
    "별도 재무상태표", "별도재무상태표",
    "재무상태표", "재 무 상 태 표"
]
capital_changes_keywords = [
        "연결자본변동표", "연결 자본변동표", "연 결 자 본 변 동 표"
        "별도 자본변동표", "별도자본변동표",
        "자본변동표", "자 본 변 동 표"
]
class MakeFinancialDataDB:
    """재무 데이터 서비스 클래스"""
    error_log_path = Path(settings.STOCKEASY_LOCAL_CACHE_DIR) / "financial_reports_error_log.txt"
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

        # 파일 핸들러 생성
        error_file_handler = logging.FileHandler(self.error_log_path, encoding='utf-8')

        # *** 중요: 파일 핸들러의 레벨을 ERROR로 설정 ***
        error_file_handler.setLevel(logging.ERROR)

       # 로그 포맷터 설정
        log_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        error_file_handler.setFormatter(log_formatter)

        # 로거에 에러 파일 핸들러 추가 (중복 추가 방지)
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(self.error_log_path) for h in logger.handlers):
             logger.addHandler(error_file_handler)
             logger.info(f"에러 로그 파일 설정 완료: {self.error_log_path}") # 이 INFO 로그는 파일에 안 감
        

        
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
    
    async def error_log(self, message: str):
        """에러 로그 저장"""
        logger.error(message)
        with open(self.error_log_path, "a") as f:
            f.write(f"{datetime.now()}: {message}\n")
    
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
        print(f"연결 포괄손익계산서 처리 시작: 기업={company_code}, 연도={report_year}, 분기={report_quarter or '연간'}, 파일={os.path.basename(report_file_path)}")
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
            
            # 파일 분석과 데이터베이스 작업을 하나의 트랜잭션으로 처리
            async with self._db.begin() as transaction:
                logger.info(f"트랜잭션 시작: {report_file_path}")
                
                # 회사 정보 조회
                #logger.info(f"기업 정보 조회 중: {company_code}")
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
                
                
                # 재무제표 섹션 키워드
                financial_statement_keywords = [
                    "연결 재무제표", "연결재무제표",
                    "재무제표"
                ]
                
                # 각 재무제표 유형 키워드
                statement_type_keywords = {
                    "balance_sheet": ["재무상태표", "연결재무상태표", "연결 재무상태표"],
                    "income_statement": ["손익계산서", "포괄손익계산서","연결 손익계산서", "연결손익계산서", "연결포괄손익계산서", "연결 포괄손익계산서"],
                    "cash_flow": ["현금흐름표", "연결현금흐름표", "연결 현금흐름표"],
                    "equity_change": ["자본변동표", "연결자본변동표", "연결 자본변동표"]
                }
                
                # 1. 목차에서 손익계산서 섹션 직접 찾기
                start_page = None
                end_page = None
                start_at_연결재무제표 = True
                for i, item in enumerate(toc):
                    level, title, page = item
                    
                    for keyword in toc_income_statement_keywords:
                        if keyword in title:
                            # 시작 페이지 설정 (목차의 페이지는 1부터 시작하지만 fitz는 0부터 시작)
                            start_page = page - 1
                            
                            # 다음 동일 레벨 또는 상위 레벨 목차 항목 찾기
                            for next_item in toc[i+1:]:
                                next_level, next_title, next_page = next_item
                                if next_level <= level:
                                    # 다음 섹션 페이지까지.를 끝 페이지로 설정
                                    end_page = next_page
                                    break
                            
                            # 다음 섹션을 찾지 못한 경우 기본적으로 시작 페이지 + 2로 설정
                            if end_page is None:
                                end_page = min(start_page + 10, len(doc) - 1)
                                
                            logger.info(f"연결 포괄손익계산서 섹션 찾음: 페이지 {start_page+1}~{end_page+1}")
                            start_at_연결재무제표 = False
                            break
                    
                    if start_page is not None:
                        break
                
                # start_page가 문서 전체 페이지의 절반을 넘어가면 잘못된 데이터로 간주
                if start_page is not None and start_page > len(doc) / 2:
                    logger.warning(f"손익계산서 섹션이 문서 후반부({start_page+1}/{len(doc)})에 위치하여 잘못된 데이터일 가능성이 높습니다. 무시합니다.")
                    start_page = None
                    end_page = None
                
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
                        search_range = 10  # 연결 재무제표 이후 15페이지까지 검색
                        search_end = min(financial_statement_page + search_range, len(doc) - 1)
                        
                        for page_num in range(financial_statement_page, search_end + 1):
                            page = doc[page_num]

                            text_list = page.get_text().split("\n")

                            for text in text_list:
                                txt_strip  = text.strip().replace(" ", "") #앞뒤 공백 및 모든 띄워쓰기 제거.
                                # 1.별도손익계산서
                                txt_strip = remove_number_prefix_toc(txt_strip)
                                # if txt_strip and page_num - financial_statement_page <= 3:
                                #     print(f"txt_strip : {txt_strip}")
                                if txt_strip in toc_income_statement_keywords:
                                    start_page = page_num
                                    end_page = min(start_page + 10, len(doc) - 1)  # 기본적으로 3페이지 범위
                                    start_at_연결재무제표 = False
                                    logger.info(f"연결 재무제표 이후에서 손익계산서 찾음: 페이지 {start_page}~{end_page}")

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
                    logger.error(f"연결 포괄손익계산서 페이지를 찾을 수 없습니다: {company_code}, {os.path.basename(report_file_path)}")
                    doc.close()
                    return {
                        "success": False,
                        "message": f"연결 포괄손익계산서 페이지를 찾을 수 없습니다: {company_code}, {os.path.basename(report_file_path)}"
                    }
                
                doc.close()
                # 2. 페이지 텍스트 추출
                extracted_tables, period_info, unit_info = await self.extract_exact_financial_data2(report_file_path, "income_statement", report_type, 
                                                                   start_page, end_page+1, start_at_연결재무제표)
                
                # 3. LLM으로 데이터 구조화
                has_llm_error, financial_items = await self._process_with_llm_and_structure_data(
                    extracted_tables, report_type, report_year, report_quarter, period_info, unit_info, company_code, report_file_path
                )
                
                # 실패 처리
                if has_llm_error:
                    logger.error(f"구조화 중 오류 발생1: {report_file_path} {has_llm_error.get('message', '알 수 없는 오류')}")
                    return has_llm_error

                # 3. 데이터 보정(누락, None, 단위)
                financial_items = await self.fill_data_missing(extracted_tables, financial_items, report_file_path, unit_info)

                # 4. 데이터베이스 저장
                logger.info(f"데이터베이스 저장 시작: 회사={company_code}, 보고서={report.id}")
                save_start_time = datetime.now()
                saved_items = await self._save_structured_data(
                    company.id, report.id, report_file_path, financial_items, income_statement_keywords
                )
                save_duration = (datetime.now() - save_start_time).total_seconds()
                logger.info(f"데이터베이스 저장 완료: {len(saved_items)}개 항목 저장, 소요시간={save_duration:.1f}초")
                
                if len(saved_items) == 0:
                    logger.error(f"데이터베이스 저장 실패: {company_code}, 보고서={report.id}, {report_year}년 {report_quarter}분기 {report_type}보고서")
                    logger.error(f"파일 : {report_file_path}")
                    pprint(financial_items, indent=4)
                    logger.error(f"==================")
                
                # 5. 보고서 처리 완료 표시
                report.processed = True
                # 명시적 커밋 제거 - 트랜잭션 블록이 종료되면 자동으로 커밋됨
                logger.info(f"보고서 처리 완료 상태로 업데이트: {report.id}")
                
                # 트랜잭션 완료 로깅
                logger.info(f"트랜잭션 완료: {report_file_path}")
            
            # 6. 캐시 무효화 (트랜잭션 외부에서 처리)
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
            text = f"연결 포괄손익계산서 처리 중 오류 발생: {company_code}, 오류={str(e)}, {report_file_path}"
            logger.error(text, exc_info=True)
            text_error = f"{report_file_path}\n{text}"
            await self.error_log(text_error)
            if self._db:
                await self._db.rollback()
            return {
                "success": False,
                "message": f"연결 포괄손익계산서 처리 중 오류 발생: {str(e)}"
            }
        
    def remove_number_prefix(self, financial_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        항목 이름과 코드에서 숫자 접두사를 제거하고 반환합니다.
        지원하는 패턴:
        - 숫자 접두사 (예: "1.", "1.2.", "1.2.3.")
        - 로마 숫자 접두사 (예: "I.", "II.", "IV.")
        - 기타 유사한 패턴
        """
        # 다양한 숫자 접두사 패턴을 처리하는 정규식
        prefix_patterns = [
            r'^\d+\.\s*',              # "1. "
            r'^\d+\.\d+\.\s*',         # "1.2. "
            r'^\d+\.\d+\.\d+\.\s*',    # "1.2.3. "
            r'^[IVXLCDMivxlcdm]+\.\s*', # 로마 숫자 "I.", "II.", "IV." 등
            r'^\(\d+\)\s*',            # "(1) "
            r'^\(\w+\)\s*',            # "(가) " 등
            r'^[a-zA-Z]\.\s*',         # "A. ", "a. " 등
        ]
        
        for item in financial_items:
            if "item_name" in item:
                # 모든 패턴을 차례로 적용
                item_name = item["item_name"]
                for pattern in prefix_patterns:
                    item_name = re.sub(pattern, '', item_name)
                item["item_name"] = item_name
                
            if "item_code" in item:
                # item_code에도 동일한 처리 적용
                item_code = item["item_code"]
                for pattern in prefix_patterns:
                    item_code = re.sub(pattern, '', item_code)
                item["item_code"] = item_code
                
        return financial_items

    def fill_none_items(self, extracted_tables: List[List[str]], financial_items: List[Dict[str, Any]], fill_key: str) -> List[Dict[str, Any]]:
        """
        financial_items를 반복하며 'value'가 None인 항목을 찾고,
        extracted_tables에서 해당 값을 조회하여 채우려고 시도합니다.

        Args:
            extracted_tables: 소스에서 추출된 테이블을 나타내는 리스트의 리스트.
                              예상 구조: 연도/분기가 있는 헤더 행, 그 뒤에 첫 번째 열에 항목 이름이 있고
                              후속 열에 값이 있는 데이터 행.
            financial_items: 각 금융 항목을 나타내는 딕셔너리 리스트, 각 항목에는
                             'item_name'과 기간별(연도, 분기) 'values' 리스트가 있음.

        Returns:
            찾은 값으로 제자리에서 수정된 financial_items 리스트.
        """
        if not extracted_tables:
            print("`extracted_tables`가 비어 있습니다. 누락된 값을 채울 수 없습니다.")
            return financial_items
        if not financial_items:
            print("`financial_items`가 비어 있습니다. 채울 항목이 없습니다.")
            return financial_items

        filled_count = 0
        items_processed = 0
        values_to_fill = 0

        #print(f"None값 채우기 :  '{fill_key}' item")
        try:
            for item_index, item in enumerate(financial_items):
                items_processed += 1
                item_name = item.get('item_name')
                if not item_name:
                    print(f"인덱스 {item_index}의 항목에 'item_name'이 없습니다. 건너뜁니다.")
                    continue

                values = item.get('values', [])
                if not isinstance(values, list): 
                    print(f"항목 '{item_name}'에 잘못된 'values' 필드(리스트 아님)가 있습니다. 건너뜁니다.")
                    continue

                for value_entry_index, value_entry in enumerate(values):
                    if not isinstance(value_entry, dict):
                        print(f"항목 '{item_name}'의 인덱스 {value_entry_index}에 잘못된 값 항목이 있습니다. 건너뜁니다.")
                        continue

                    # 'value' 키가 존재하고 None인지 확인
                    if fill_key in value_entry and value_entry[fill_key] is None:
                        values_to_fill += 1

                        #print(f"항목 none : {item_name}")

                        # 추출된 테이블에서 해당 값 찾기 시도
                        # logging.info(f"'{item_name}' - 연도: {year}, 분기: {quarter}의 값 채우기 시도")
                        found_value = self._find_value_in_tables_income_statement(extracted_tables, item_name, fill_key, 0)

                        if found_value is not None:
                            # TODO: 단위 일관성 확인 - value_entry['unit'] (예: '원')와
                            # 찾은 값의 단위 비교 (더 나은 단위 구문 분석 필요).
                            # 현재는 found_value가 올바른 단위('원')라고 가정합니다.
                            value_entry[fill_key] = found_value
                            filled_count += 1
                            # logging.info(f"'{item_name}' ({year} Q{quarter})의 값을 성공적으로 채웠습니다: {found_value}")
                        else:
                            value_entry[fill_key] = 0
                            # 값을 찾거나 구문 분석할 수 없는 경우 기록
                            #print(f"추출된 테이블에서 '{item_name}' 값을 찾거나 구문 분석할 수 없습니다. 0으로 채움")
                    # else: 값이 존재하거나 fill_key 키가 없음 -> 아무 작업 안 함
        except Exception as e:
            print(f"none 채우기 오류 발생: {e}")


        print(f"None 값 채우기 완료. 처리된 항목 수: {items_processed}")
        print(f"{values_to_fill}개의 None 값을 채우려고 시도했습니다. 성공적으로 채운 수: {filled_count}")

        # 리스트는 제자리에서 수정되지만, 반환하는 것이 관례적임
        return financial_items

    def _find_value_in_tables_income_statement(self, extracted_tables, item_name, fill_key, default_value=0) -> str:

        target_idx = 1 # 'value'
        if fill_key == 'cumulative_value':
            target_idx = 2
        for table in extracted_tables:
            #print(f"[_find_value_in_tables] table : {table}, {target_idx}")
            if table[0] and item_name in table[0]:
                #print(f"[_find_value_in_tables] 찾음 [{fill_key}] : {item_name}  -> {table[target_idx]}")
                if table[target_idx]:
                    try:
                        vv = _process_numeric_value(table[target_idx])
                        return vv
                    except Exception as e:
                        print(f"[_find_value_in_tables] 오류 발생: {table[target_idx]} : {e}")
                        return default_value
                else:
                    #print(f"[_find_value_in_tables] 찾음 : {item_name}  -> None")
                    return default_value
        return default_value
    
    def check_table_type_income_statement(self, table: List[List[str]]) -> str:
        """
        손익계산서 항목 중에서 금융, 은행항목인지 확인 후 반환합니다.
        """
        table_type_full_match = {
            "순이자이익": "bank",
            "Ⅰ. 순이자이익": "bank",
            "I. 순이자이익": "bank",
            "1. 순이자이익": "bank",
            "이자수익": "bank",
            "이자비용": "bank",
            "순수수료이익": "bank",
            "이자손실": "bank",
            "이자손익": "bank",
            "이자손실": "bank",
            "이자손익": "bank",
            "이자손실": "bank",
        }
        for row in table:
            #item_name = row[0]
            item = row[0].split(" ")
            if len(item) > 0:
                item_name = item[-1] # 마지막 항목
            else:
                item_name = row[0]
            
            if item_name in table_type_full_match:
                print(f"테이블 타입 확인[금융, 은행항목]: {item_name} -> {table_type_full_match[item_name]}")
                return table_type_full_match[item_name]
        
        return None
    def check_table_type(self, table: List[List[str]]) -> str:
        """
        테이블 타입을 확인하고 반환합니다.
        """
        table_type_full_match = {
            "매출액": "income_statement",
            "매출원가": "income_statement",
            "매출총이익": "income_statement",
            "법인세비용": "income_statement",
            "주당이익": "income_statement",
            "주당손익": "income_statement",
            "주당손실": "income_statement",
            "포괄손익": "income_statement",
            "포괄이익": "income_statement",

            "부채총계": "balance_sheet",
            "자본총계": "balance_sheet",
        }
        for row in table:
            item_name = row[0]
            #print(f"item_name: {item_name}")
            if item_name in table_type_full_match:
                print(f"테이블 타입 확인: {item_name} -> {table_type_full_match[item_name]}")
                return table_type_full_match[item_name]
            
        for row in table:
            if not row[0]: 
                continue
            item_name = row[0].replace(" ", "")
            #print(f"item_name: {item_name}")
            if item_name in table_type_full_match:
                print(f"테이블 타입 확인[공백제거후]: {item_name} -> {table_type_full_match[item_name]}")
                return table_type_full_match[item_name]
        
        return None
    
    async def extract_exact_financial_data2(self, report_file_path: str, 
                                           statement_type: str, 
                                           report_type: str, 
                                           start_page: int, end_page: int, start_at_연결재무제표: bool = False) :
        all_text = ""
        # start_page는 정확하게 찾았으니까. 마지막 키워드 감지해서 정확한 테이블 추출.
        # fitz 대신 pdfplumber 사용하여 텍스트 추출
        logger.info(f"페이지 텍스트 추출 시작: 페이지 {start_page}~{end_page}")
        all_data = []
        with pdfplumber.open(report_file_path) as pdf:
            for page_num in range(start_page, end_page):
                #logger.info(f"패아지 : {page_num}")
                
                page = pdf.pages[page_num]
                text = page.extract_text()
                tables = page.extract_tables()
                all_data.append([page_num, text, tables])
                
                if text:
                    text = re.sub(r'.*전자공시시스템 dart\.fss\.or\.kr.*(\n|$)', '', text)
                if text:
                    all_text += text
        
        extracted_tables, period_info, unit_info = self.extract_exact_financial_data_in2(all_data, statement_type, report_file_path, start_at_연결재무제표)
        extracted_tables_removed = self.remove_newline_in_table(extracted_tables)
        #extracted_table_text = "\n".join([str(tables) for _, _, tables in extracted_data])

        print(f"period_info: {period_info}")
        print(f"unit_info: {unit_info}")
        #print(f"extracted_tables: {extracted_tables_removed}")

        return extracted_tables_removed, period_info, unit_info
    
    def extract_exact_financial_data_in2(self, all_data: List[Tuple[int, str, List[List[str]]]], statement_type, report_file_path, start_at_연결재무제표: bool = False):
        """
        텍스트에서 정확히 재무제표 키워드만 있는 라인을 찾아 해당 위치부터 텍스트를 추출합니다.
        """
        # 시작 추출
        # start word가 판별되면, 해당

        start_keyword = income_statement_keywords
        end_keyword = []
        extracted_tables = []
        start_line = -1
        start_page = -1
        found_keyword_end = None
        end_page = -1

        extract_index_start = -1
        extract_index_end = -1
        logger.info(f"extract_exact_financial_data_in2 : start_at_연결재무제표={start_at_연결재무제표}")
        if start_at_연결재무제표:
            bOnTryFindStartKeyword = False
        else:
            bOnTryFindStartKeyword = True
        for all_data_index, data in enumerate(all_data):
            page, text, tables = data
            #print(f"page: {page}")
            # print(f"end keyword : {end_keyword}")
            #print(text)
            # 라인별로 분리
            lines = text.split('\n')
            
            end_line = len(text)

            
            # 각 라인에 대해 정확히 키워드만 있는지 확인
            b연결 = False
            
            keyword = ['연결재무제표', '연결재무상태표', '연결재무상태표']
            if start_page == -1: # 시작 문자열 찾기.
                for i, line in enumerate(lines):
                    stripped_line = remove_number_prefix_toc(line)
                    #print(f"test : {stripped_line}")
                    if start_at_연결재무제표 and stripped_line in keyword and not bOnTryFindStartKeyword:
                        bOnTryFindStartKeyword = True
                        logger.info(f"연결재무제표 시작 - 연결재무제표/재무상태 발견: {stripped_line}")

                    if not bOnTryFindStartKeyword:
                        continue
                    

                    if stripped_line in start_keyword:
                        #logger.info(f"start keyword 발견11: {stripped_line}")
                        start_line = i
                        start_page = page
                        found_keyword_start = stripped_line
                        if "연결" in stripped_line:
                            b연결 = True
                        break

                    for keyword in start_keyword:
                        # 정규식 패턴 생성 - 공백이 추가되거나 다른 문자가 있을 수 있음을 고려
                        # 예: "재무상태표" -> ".*재무.*상태.*표.*"
                        # 또는 더 단순하게 문자열 포함 여부 확인
                        pattern = f".*{keyword}.*"
                        #print(f"패턴체크 : {keyword}")
                        if re.search(pattern, stripped_line, re.IGNORECASE):
                            #print(f"end keyword 체크 : '{stripped_line}', 키워드:'{keyword}', 시작페이지:{start_page}, 현재페이지 {page}")
                            if start_page <= page: # start보다 뒤쪽에서 만나야제.
                                start_line = i
                                start_page = page
                                found_keyword_start = stripped_line
                                break
                    if start_page >= 0:
                        break
                if start_page == -1: # 못찾았으면
                    continue

            if start_page >= 0 and extract_index_start == -1:
                logger.info(f"start keyword 발견 : '{found_keyword_start}', 페이지 {page}, 라인 {start_line+1}, 연결={b연결}, start연결재무제표={start_at_연결재무제표}")
                extract_index_start = all_data_index
                # 시작 페이지의 마지막 테이블만 추가. 시작페이지의 마지막 테이블은 항상 해당 재무테이블이므로.
                
                if tables and len(tables) > 0:
                    # 마지막 테이블만 추가
                    # 안됨. 손익계산서, 포괄 손익계산서 테이블이 연달아 나올수 있음.
                    for x, table in enumerate(tables):
                        table_type = self.check_table_type(table)
                        if table_type != "balance_sheet": # 재무상태표가 아니면 추가.
                            extracted_tables.extend(table)

                    logger.info(f"시작페이지 마지막 테이블 추출: 테이블 크기={len(tables[-1]) if tables[-1] else 0}행")

                
                # 추가: start keyword 발견 후부터 '단위 :' 패턴을 찾을 때까지 텍스트 추출
                found_pattern = False
                period_lines = []
                for j, line in enumerate(lines[start_line+1:], start=start_line+1):
                    if "전자공시시스템 dart.fss.or.kr" in line:
                        continue
                    period_lines.append(line)
                    # 단위 패턴 찾기
                    unit_pattern = re.search(r'\(\s*단위\s*:\s*([^\)]+)\s*\)', line)
                    if unit_pattern:
                        # 단위 정보 저장
                        unit_info = unit_pattern.group(1).strip()
                        logger.info(f"단위 정보 발견: '{unit_info}'")
                        if unit_info == "USD":
                            logger.info(f"!!! 단위 정보 USD !!! : {unit_info}")
                        
                        # 단위 패턴 이전까지의 텍스트를 기간 정보로 저장
                        period_info = '\n'.join(lines[start_line+1:j])
                        logger.info(f"기간 정보 추출: '{period_info}'")
                        found_pattern = True
                        break
                if not found_pattern:
                    # 검색 실패 시 다음 페이지로 넘어가버린것.
                    next_page_idx = all_data_index + 1
                    _page, _text, _tables = all_data[next_page_idx]
                    _lines = _text.split('\n')
                    for j, line in enumerate(_lines):
                        
                        period_lines.append(line)
                        unit_pattern = re.search(r'\(\s*단위\s*:\s*([^\)]+)\s*\)', line)
                        if unit_pattern:
                            # 단위 정보 저장
                            unit_info = unit_pattern.group(1).strip()
                            logger.info(f"[다음페이지] 단위 정보 발견: '{unit_info}'")
                            # 단위 패턴 이전까지의 텍스트를 기간 정보로 저장
                            period_info = '\n'.join(period_lines[:-1])
                            logger.info(f"[다음페이지] 기간 정보 추출: '{period_info}'")
                            found_pattern = True
                            break


            start_keyword, end_keyword = self.get_keyword_start_and_end_toc(statement_type)

            # 목차는 각 항목이 단일 라인으로 이루어져있다. 
            # 1. 연결 포괄 손익계산서
            # A. 자본변동표 

            # 각 라인에 대해 정확히 키워드만 있는지 확인
            #print(f"--- {page} ---\n{lines}")
            tot_lines = len(lines)
            skip_자본변동표 = False
            for i, line in enumerate(lines):
                stripped_line = remove_number_prefix_toc(line)
                # 기존 정확한 매칭 방식 우선 적용
                if stripped_line in end_keyword :
                    if start_page == page and i < start_line: # 같은 페이지, 시작 키워드보다 이전에서 찾은건 패스
                        continue
                    print(f"end keyword 체크(정확 매칭) : [{i}/{tot_lines}] '{stripped_line}', 시작페이지:{start_page}, 현재페이지 {page}")
                    diff = tot_lines - i
                    if tot_lines > 30 and diff <= 7: # end keyword가 뒤에서 5번째줄 안쪽에 나타난거면, 자본변동표 분석 스킵
                        print("자본변동표 분석 스킵")
                        skip_자본변동표 = True
                    if start_page <= page: # start보다 뒤쪽에서 만나야제.
                        found_keyword_end = stripped_line
                        extract_index_end = all_data_index
                        break

                # 정확한 패턴 매칭 대신 정규식 사용
                if not found_keyword_end:
                    for keyword in end_keyword:
                        # 정규식 패턴 생성 - 공백이 추가되거나 다른 문자가 있을 수 있음을 고려
                        # 예: "재무상태표" -> ".*재무.*상태.*표.*"
                        # 또는 더 단순하게 문자열 포함 여부 확인
                        pattern = f".*{keyword}.*"
                        #print(f"패턴체크 : {keyword}")
                        if re.search(pattern, stripped_line, re.IGNORECASE):
                            logger.info(f"end keyword 체크 : '{stripped_line}', 키워드:'{keyword}', 시작페이지:{start_page}, 현재페이지 {page}")
                            if start_page <= page: # start보다 뒤쪽에서 만나야제.
                                found_keyword_end = stripped_line
                                extract_index_end = all_data_index
                                break
                
            before_length = len(extracted_tables)
            if page != start_page: #첫페이지는 처음에 넣었음. #마지막 페이지 테이블 분류 실패.
                for x, table in enumerate(tables):
                    extracted_tables.extend(table)
            if found_keyword_end and not skip_자본변동표:
                extracted_tables = extracted_tables[:before_length]

                # 마지막 테이블 처리.
                print(f"end keyword 발견 : '{found_keyword_end}', 시작페이지:{start_page}, 현재페이지 {page} => [{start_page}:{page}], before_length={before_length}")
                

            # 테이블 내에서 found_keyword_end와 일치하는 항목 찾기
                keyword_found_in_table = False
                keyword_table_index = -1
                # end 테이블은 테이블 내의 요소를 검색하기 때문에 정확하게 검색.
                table_자본변동표 = ["기초자본", "자본 합계", "총자본", "기타자본", "자본잉여금", "연결자본잉여금", "연결 자본잉여금", "연결자본조정", "연결 자본조정"]
                # 각 테이블 확인
                cond_자본변동표 = [ '자본', None, None ]
                for t_idx, table in enumerate(tables):
                    # 2차원 배열(테이블) 내에서 키워드 찾기
                    found_자본 = False
                    cnt_none = 0
                    for row in table:
                        for cell in row:
                            if isinstance(cell, str):
                                _cell = cell.replace("\n", "")
                                if _cell.strip() in table_자본변동표:
                                    keyword_found_in_table = True
                                    keyword_table_index = t_idx
                                    print(f"테이블 내에서 종료 키워드 발견: '{cell}', 테이블 인덱스={t_idx}, 페이지={page}")
                                    break
                        if not keyword_found_in_table:
                            # 자본변동표는 [ '자본', None, None ] 패턴이면 자본변동표.
                            for i in range(len(row)-2):  # 마지막 2개 셀은 검사 불필요
                                if (isinstance(row[i], str) and 
                                    row[i].replace("\n", "").strip() == "자본" and
                                    row[i+1] is None and 
                                    row[i+2] is None):
                                    keyword_found_in_table = True
                                    keyword_table_index = t_idx
                                    print(f"자본변동표 패턴 발견: '{row[i]}', None, None - 테이블 인덱스={t_idx}, 페이지={page}")
                                    break

                        if keyword_found_in_table:
                            break
                    if keyword_found_in_table:
                        break
                
                # 종료 키워드가 테이블 내에 있으면 해당 테이블 이전까지만 추가
                if keyword_found_in_table and keyword_table_index > 0:
                    # 종료 키워드가 포함된 테이블 이전까지만 추가
                    for t_idx in range(keyword_table_index):
                        extracted_tables.extend(tables[t_idx])
                        #print(f"테이블 추가[{t_idx}]: {tables[t_idx]}")
                    print(f"종료 키워드가 포함된 테이블 이전 {keyword_table_index}개 테이블 추가")
                elif keyword_table_index == 0:
                    #종료 키워드의 테이블의 인덱스가 0이면, 손익계산서 테이블은 이전 페이지에서 끝났기 때문에, 따로 추가처리를 하지 않는다.
                    print(f"종료 키워드가 테이블 idx 0, 테이블 추가하지 않음.")
                elif not found_keyword_end:
                    # 종료 키워드가 없으면 모든 테이블 추가
                    for table in tables:
                        extracted_tables.extend(table)
                    print(f"종료 키워드 없음, 현재 페이지의 모든 테이블({len(tables)}개) 추가")                
                
                break

        if start_line == -1:
            start_line = 0
        if extract_index_start == -1:
            logger.error(f"start keyword 발견 실패 !! 파일: {os.path.basename(report_file_path)}")
        if extract_index_end == -1:
            extract_index_end = len(all_data) -1 
            logger.error(f"end keyword 발견 실패 !! 파일: {os.path.basename(report_file_path)}")
        if not period_info:
            logger.error(f"period_info 발견 실패 !! 파일: {os.path.basename(report_file_path)}")
        print(f"extracted_tables:\n{extracted_tables}")
        # 넘겨받은 데이터의 정확한 테이블만 반환.
        return extracted_tables, period_info, unit_info
    
    def remove_newline_in_table(self, tables):
        """
        테이블 데이터에서 줄바꿈 문자를 제거합니다.
        
        Args:
            tables: 테이블 데이터(2차원 또는 3차원 리스트)
            
        Returns:
            줄바꿈이 제거된 테이블 데이터
        """
        logger.info(f"줄바꿈 문자 제거 시작: 테이블 개수={len(tables)}")
        
        # 리스트를 깊은 복사
        processed_tables = []
        
        for table_idx, table in enumerate(tables):
            processed_table = []
            
            if not isinstance(table, list):
                # 테이블이 리스트가 아닌 경우, 원본 반환
                #logger.info(f"리스트 아님: {type(table)}")
                processed_tables.append(table)
                continue
                
            for row_idx, row in enumerate(table):
                processed_row = []
                
                if not isinstance(row, list):
                    # 행이 리스트가 아닌 경우, 원본 행 사용
                    processed_row = row
                    #logger.info(f"원본 행 사용: {type(row)}")
                    if isinstance(row, str):
                        # 줄바꿈 문자만 제거 (\n, \r)
                        processed_row = row.replace('\n', '').replace('\r', '')
                else:
                    for cell_idx, cell in enumerate(row):
                        # if cell and "관계회사지분" in cell:
                        #     print(f"관계회사지분 발견: {cell}, type: {type(cell)}")
                        # if cell :
                        #     print(f"cell: {cell}, type: {type(cell)}")
                        if isinstance(cell, str):
                            # 줄바꿈 문자만 제거 (\n, \r)
                            new_cell = cell.replace('\n', '').replace('\r', '')
                            # if cell != new_cell:
                            #     logger.info(f"줄바꿈 제거: '{cell}' → '{new_cell}'")
                            processed_row.append(new_cell)
                        else:
                            processed_row.append(cell)
                
                processed_table.append(processed_row)
            
            processed_tables.append(processed_table)
            
        logger.info(f"줄바꿈 문자 제거 완료: 테이블 개수={len(processed_tables)}")
        return processed_tables


    def get_keyword_start_and_end_toc(self, statement_type):
        # if statement_type == "income_statement":
        #     start_keyword = income_statement_keywords
        #     end_keyword = cash_flow_keywords + balance_sheet_keywords + capital_changes_keywords
        # elif statement_type == "cash_flow":
        #     start_keyword = cash_flow_keywords
        #     end_keyword = income_statement_keywords + balance_sheet_keywords + capital_changes_keywords
        # elif statement_type == "balance_sheet":
        #     start_keyword = balance_sheet_keywords
        #     end_keyword = income_statement_keywords + cash_flow_keywords + capital_changes_keywords
        # elif statement_type == "capital_changes":
        #     start_keyword = capital_changes_keywords
        #     end_keyword = income_statement_keywords + cash_flow_keywords + balance_sheet_keywords
        # return start_keyword, end_keyword
        if statement_type == "income_statement":
            start_keyword = toc_income_statement_keywords
            end_keyword = toc_cash_flow_keywords + toc_balance_sheet_keywords + toc_capital_changes_keywords
        elif statement_type == "cash_flow":
            start_keyword = toc_cash_flow_keywords
            end_keyword = toc_income_statement_keywords + toc_balance_sheet_keywords + toc_capital_changes_keywords
        elif statement_type == "balance_sheet":
            start_keyword = toc_balance_sheet_keywords
            end_keyword = toc_income_statement_keywords + toc_cash_flow_keywords + toc_capital_changes_keywords
        elif statement_type == "capital_changes":
            start_keyword = toc_capital_changes_keywords
            end_keyword = toc_income_statement_keywords + toc_cash_flow_keywords + toc_balance_sheet_keywords
        return start_keyword, end_keyword
    
    
    async def extract_exact_financial_data(self, report_file_path: str, 
                                           statement_type: str, 
                                           report_type: str, 
                                           start_page: int, end_page: int) -> Dict[str, Any]:
        all_text = ""
        # start_page는 정확하게 찾았으니까. 마지막 키워드 감지해서 정확한 테이블 추출.
        # fitz 대신 pdfplumber 사용하여 텍스트 추출
        logger.info(f"페이지 텍스트 추출 시작: 페이지 {start_page}~{end_page}")
        with pdfplumber.open(report_file_path) as pdf:
            for page_num in range(start_page, end_page):
                #logger.info(f"패아지 : {page_num}")
                if page_num < len(pdf.pages):
                    
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    #table = page.extract_tables()
                    #table = page.extract_table()
                    #print(f"table[{page_num}][{len(table)}]: {table}")
                    if text:
                        text = re.sub(r'.*전자공시시스템 dart\.fss\.or\.kr.*(\n|$)', '', text)
                    if text:
                        all_text += text
        
        all_text = self.extract_exact_financial_data_in(all_text, statement_type)

        return all_text
    

    async def _save_structured_data(
        self, company_id: int, report_id: int, report_file_path: str, financial_items: List[Dict[str, Any]], keywords: List[str]
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
        logger.info(f"current_report : {current_report}")
        if not current_report:
            logger.error(f"보고서를 찾을 수 없습니다: ID={report_id}")
            return saved_items
        

        if not financial_items:
            logger.error(f"데이터 구조화에 실패했습니다: {company_id}, {report_id}")
            return saved_items
            
        current_year = current_report.report_year
        current_quarter = current_report.report_quarter
        current_year_month = current_report.year_month
        
        logger.info(f"데이터 저장 시작: 연도={current_year}, 분기={current_quarter or '연간'}, 파일={report_file_path}")
       
        # 재무제표 유형 식별
        statement_type_mapping = self._identify_statement_type(keywords)
        
        # 오류 발생 시 프로그램 중단 플래그
        errors_detected = False
        
        #for item in structured_data.get("financial_summary", []):
        for item in financial_items:
            if errors_detected:
                logger.error(f"오류 발생 후 중단: {item.get('item_name')}")
                break
                
            item_name = item.get("item_name")
            item_code = item.get("item_code")

            # item_name에서 주석 (주X,Y..) 패턴 제거
            cleaned_item_name = item_name
            if item_name:
                # 정규식을 사용하여 '(주숫자,숫자...)' 패턴 및 앞뒤 공백 제거
                cleaned_item_name = remove_comment_number(item_name)
                cleaned_item_name = re.sub(r'\s*\(주[\d,]+\)\s*', '', item_name).strip() # (주 숫자) 패턴
                cleaned_item_name = re.sub(r'<주석\s*\d+>', '', cleaned_item_name).strip() # <주석 숫자> 패턴 제거
                
                cleaned_item_name = cleaned_item_name.replace("(손실)", "")
                cleaned_item_name = cleaned_item_name.replace("(수익)", "")
                

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
                #logger.info(f"카테고리 결정: {category}")
                # 항목 매핑 조회 또는 생성
                item_mapping = await repo.get_item_mapping_by_code(item_code)
                if not item_mapping:
                    # standard_name에는 정리된 이름(cleaned_item_name) 사용
                    logger.info(f"새 항목 매핑 생성: {item_code}, 표준명: {cleaned_item_name} (원본: {item_name})")
                    item_mapping = await repo.create_item_mapping(
                        item_code=item_code,
                        category=category,
                        standard_name=cleaned_item_name # 정리된 이름 사용
                    )

                # 원본 항목명 매핑 저장 (원본 item_name과 item_mapping의 standard_name 비교)
                # RawMapping에는 원본(정리 전) item_name 저장
                if item_name != item_mapping.standard_name:
                    await repo.create_raw_mapping(item_mapping.id, item_name) # 원본 이름 저장

                # 데이터 값 저장 루프
                for value_data in item.get("values", []):
                    data_year = value_data.get("year")
                    data_quarter = value_data.get("quarter")
                    value = value_data.get("value", 0)
                    period_value = value
                    cumulative_value = value_data.get("cumulative_value", 0)
                    unit = value_data.get("unit", "원")
                    
                    if value is None:
                        value = 0
                        continue
                    
                  
                    # 4분기의 경우, 누적 데이터밖에 없으므로
                    # 3분기에서 빼야됨.
                    # 연월 계산
                    data_year_month = data_year * 100
                    if data_quarter:
                        data_year_month += data_quarter * 3
                    else:
                        data_year_month += 12

                    # 4분기의 경우, 누적 데이터밖에 없으므로 3분기에서 빼야함
                    if data_quarter == 4 or (data_quarter is None and data_year_month % 100 == 12):
                        # 3분기 데이터 조회
                        prev_quarter = 3
                        prev_year_month = data_year * 100 + prev_quarter * 3
                        
                        # 이전 분기 데이터 조회
                        prev_data = await self._get_previous_quarter_data_by_type(
                            company_id, item_mapping.id, prev_year_month, statement_type
                        )
                        
                        if prev_data and prev_data.cumulative_value is not None and cumulative_value is not None:
                            # 단위 확인
                            current_unit = value_data.get('unit', '원')
                            prev_unit = prev_data.display_unit if hasattr(prev_data, 'display_unit') else '원'
                            
                            # 형변환: Decimal과 float 간 연산을 위한 타입 통일
                            current_value = float(cumulative_value)
                            prev_value = float(prev_data.cumulative_value)
                            
                            # 단위가 다른 경우 원 단위로 변환
                            if current_unit != prev_unit:
                                # 원 단위로 변환
                                current_value_won = self._convert_to_won(current_value, current_unit)
                                prev_value_won = self._convert_to_won(prev_value, prev_unit)
                                
                                # 원 단위로 계산
                                value_won = current_value_won - prev_value_won
                                
                                # 결과를 4분기의 원래 단위로 다시 변환
                                value = self._convert_from_won(value_won, current_unit)
                            else:
                                # 단위가 같은 경우 단순 계산
                                value = current_value - prev_value
                            
                            period_value = value
                            logger.info(f"4분기 데이터 계산: {category}, {data_year_month}, item={cleaned_item_name} 값={value} (누적값={cumulative_value}, 3분기 누적값={prev_data.cumulative_value}, 단위: 현재={current_unit}, 이전={prev_unit})")

                    
                    # 재무제표 유형에 따라 적절한 테이블에 저장
                    financial_data = await self._save_to_appropriate_table(
                        report_id, company_id, item_mapping.id, data_year_month,
                        value, unit, cumulative_value, period_value, is_cumulative,
                        statement_type, category, cleaned_item_name, report_file_path
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
                
                # 오류를 다시 발생시켜 상위 호출자에게 전파
                raise
        
        # 명시적인 커밋은 상위 함수인 process_financial_summary에서 수행
        logger.info(f"데이터 저장 완료: {len(saved_items)}개 항목")
        
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
            "포괄손익계산서": {"type": "comprehensive_income", "is_cumulative": True},
            "연결포괄손익계산서": {"type": "comprehensive_income", "is_cumulative": True},
            "별도포괄손익계산서": {"type": "comprehensive_income", "is_cumulative": True},
            "연결손익계산서": {"type": "income_statement", "is_cumulative": True},
            "별도손익계산서": {"type": "income_statement", "is_cumulative": True},            
            "손익계산서": {"type": "income_statement", "is_cumulative": True},            
            
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
        
    
        
    async def _save_to_appropriate_table(self, report_id, company_id, item_id, year_month, 
                                       value, unit, cumulative_value, period_value, 
                                       is_cumulative, statement_type, category, item_name, report_file_path) -> Any:
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
        elif "포괄손익계산서" in category:
            # 포괄손익계산서 테이블에 저장 (손익계산서 테이블과 동일)
            logger.info(f"포괄손익계산서 항목 저장: {item_name}, 값={value}, 누적:{cumulative_value}, 단위:{unit}")
            financial_data = await repo.save_income_statement_data(
            #financial_data = await repo.compare_income_statement_data(
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

            # print(f"company:{company_id}, item:{item_id}, year_month:{year_month}, report_id:{report_id}, value:{value}, unit:{unit}, cumulative_value:{cumulative_value}")
            # print(f"비교결과: 모든 값일치({financial_data['matches']})")
            # if not financial_data['matches']:
            #     print(f"{financial_data['differences']}")

            # with open("compare.log", "a+", encoding="utf-8") as file:
            #     file.write(f"포괄손익계산서 항목 저장: 일치({financial_data['matches']}), {item_name}, 값={value}, 누적:{cumulative_value}, 단위:{unit}\n")
            #     if not financial_data['matches']:
            #         file.write(f"  {financial_data['differences']}\n")                    

        elif "손익계산서" in category:
            # 손익계산서 테이블에 저장
            logger.info(f"손익계산서 항목 저장: {item_name}, 값={value}, 누적:{cumulative_value}, 단위:{unit}")
            financial_data = await repo.save_income_statement_data(
            #financial_data = await repo.compare_income_statement_data(
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
            # print(f"company:{company_id}, item:{item_id}, year_month:{year_month}, report_id:{report_id}, value:{value}, unit:{unit}, cumulative_value:{cumulative_value}")
            # print(f"비교결과: 모든 값일치({financial_data['matches']})")
            # if not financial_data['matches']:
            #     print(f"{financial_data['differences']}")
            # with open("compare.log", "a+", encoding="utf-8") as file:
            #     file.write(f"포괄손익계산서 항목 저장: 불일치({financial_data['matches']}), {item_name}, 값={value}, 누적:{cumulative_value}, 단위:{unit}\n")
            #     if not financial_data['matches']:
            #         file.write(f"  {financial_data['differences']}\n")                        
            
       
            
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
            logger.info(f"catergory 지정 실패: {category}, 값={value} {unit}")
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

    def _convert_to_won(self, value, unit):
        if unit == '원':
            return value
        elif unit == '천원':
            return value * 1000
        elif unit == '백만원':
            return value * 1000000
        elif unit == '십억원':
            return value * 1000000000
        # 필요한 다른 단위 변환 추가
        return value

    def _convert_from_won(self, value_won, target_unit):
        if target_unit == '원':
            return value_won
        elif target_unit == '천원':
            return value_won / 1000
        elif target_unit == '백만원':
            return value_won / 1000000
        elif target_unit == '십억원':
            return value_won / 1000000000
        # 필요한 다른 단위 변환 추가
        return value_won

    async def _check_and_add_missing_essential_indicators(self, financial_items: List[Dict[str, Any]], report_file_path: str) -> List[Dict[str, Any]]:
        """핵심 재무 지표(매출액, 영업이익, 당기순이익)가 누락된 경우 찾아서 추가하는 함수"""
        essential_codes = ["net_income", "revenue", "operating_income"]
        found_essentials = set(item.get("item_code") for item in financial_items)
        keywords = {
            "net_income": "당기순이익", 
            "revenue": "매출액", 
            "operating_income": "영업이익"
        }

        for code in essential_codes:
            found_code_items = []
            if code in found_essentials:
                continue
                
            logger.warning(f"핵심 지표 누락: {code}")
            logger.warning(f"파일: {report_file_path}")

            # 키워드를 포함하는 항목 찾기
            for item in financial_items:
                if code in item.get("item_code", ""):
                    year = item.get("values")[0].get("year", 0)
                    quarter = item.get("values")[0].get("quarter", 0)
                    logger.warning(f"'{keywords[code]}'가 포함된 항목 발견: {year}년 {quarter}분기 {item.get('item_code')} -> {item.get('item_name')}, {item.get('values')[0].get('value', 0)}")
                    found_code_items.append(item)
            
            if len(found_code_items) > 0:
                logger.warning(f"핵심 지표 누락 항목 찾음. 병합 시도: {code}, {len(found_code_items)}개 항목")
                values = 0
                cumulative_values = 0
                
                for item in found_code_items:
                    # 항목의 값 누적
                    values += item.get("values")[0].get("value", 0)
                    cumulative_values += item.get("values")[0].get("cumulative_value", 0)
                    quarter = item.get("values")[0].get("quarter", 0)
                    unit = item.get("values")[0].get("unit", "")
                    year = item.get("values")[0].get("year", 0)
                    
                add_item = {
                    "item_code": code, 
                    "item_name": keywords[code], 
                    "values": [{ 
                        "value": values, 
                        "cumulative_value": cumulative_values,
                        "quarter": quarter, 
                        "unit": unit, 
                        "year": year
                    }]
                }
                #pprint(add_item, indent=4)
                financial_items.append(add_item)
                logger.warning(f"병합 결과: {code} = {values}")
                #pprint(financial_items, indent=4)
                
        return financial_items

    async def _process_with_llm_and_structure_data(self, extracted_tables, report_type, report_year, 
                                                 report_quarter, period_info, unit_info, company_code, report_file_path):
        """LLM을 사용하여 추출된 테이블 데이터를 구조화하는 함수"""
        logger.info(f"LLM을 사용한 데이터 구조화 시작 : {len(extracted_tables)}개 테이블")
        llm_start_time = datetime.now()
        financial_items = []
        
        chunk_size = 60
        all_financial_summaries = []
        has_llm_error = False
        error_details = None

        # 병렬 처리를 위한 함수 정의
        async def process_chunk(chunk_index, chunk_data):
            start_idx = chunk_index * chunk_size + 1
            end_idx = min(start_idx + len(chunk_data) - 1, len(extracted_tables))
            logger.info(f"테이블 청크 병렬 처리 중: {start_idx}-{end_idx} / {len(extracted_tables)}")
            
            structured_data_chunk = await self.llm_service.structure_income_statement_table2(
                report_type, report_year, report_quarter, str(chunk_data), period_info, unit_info
            )
            
            chunk_result = {
                "index": chunk_index,
                "range": f"{start_idx}-{end_idx}",
                "success": "error" not in structured_data_chunk,
                "data": structured_data_chunk
            }
            
            if "error" in structured_data_chunk:
                logger.error(f"청크 {chunk_index + 1} 데이터 구조화 실패: {company_code}, 오류: {structured_data_chunk.get('error')}")
                text_error = f"Chunk {chunk_index + 1} failed: {report_file_path}\n{structured_data_chunk.get('error')}"
                await self.error_log(text_error)
            else:
                financial_summary_chunk = structured_data_chunk.get("financial_summary", [])
                if financial_summary_chunk:
                    logger.info(f"청크 {chunk_index + 1} 처리 완료: {len(financial_summary_chunk)}개 항목")
                else:
                    logger.warning(f"청크 {chunk_index + 1} 처리 결과에 'financial_summary'가 없거나 비어있습니다.")
            
            return chunk_result

        # 병렬 처리를 위한 작업 생성
        chunks = []
        chunk_tasks = []
        
        for i in range(0, len(extracted_tables), chunk_size):
            chunk = extracted_tables[i:i + chunk_size]
            chunks.append(chunk)
            chunk_tasks.append(asyncio.create_task(process_chunk(i // chunk_size, chunk)))
        
        # 모든 청크를 병렬로 처리
        chunk_results = await asyncio.gather(*chunk_tasks)
        
        # 결과 병합
        for result in chunk_results:
            if not result["success"]:
                has_llm_error = True
                error_details = result["data"]
            else:
                financial_summary_chunk = result["data"].get("financial_summary", [])
                if financial_summary_chunk:
                    all_financial_summaries.extend(financial_summary_chunk)
                    logger.info(f"청크 {result['index'] + 1} (범위 {result['range']}) 결과 병합: {len(financial_summary_chunk)}개 항목")

        llm_duration = (datetime.now() - llm_start_time).total_seconds()
        
        # 모든 청크 처리 후 최종 structured_data 구성
        structured_data = {"financial_summary": all_financial_summaries}

        # 하나 이상의 청크에서 오류가 발생했는지 확인
        if has_llm_error and not all_financial_summaries: # 오류가 있었고, 성공한 데이터가 전혀 없는 경우
            logger.error(f"모든 청크에서 데이터 구조화에 실패했습니다: {company_code}")
            return None, None
        elif has_llm_error:
             logger.warning(f"일부 청크에서 데이터 구조화 오류가 발생했지만, {len(all_financial_summaries)}개의 항목을 처리했습니다.")

        # LLM 호출에 성공했거나, 일부 실패했지만 데이터가 있는 경우 계속 진행
        financial_items = structured_data.get("financial_summary", [])
        logger.info(f"LLM 데이터 구조화 완료: 총 {len(financial_items)}개 항목 식별 (일부 오류 발생 가능), 소요시간={llm_duration:.1f}초")
        pprint(financial_items, indent=2)
        
        if not financial_items and not has_llm_error: # 오류 없이 결과가 없는 경우
            logger.warning(f"LLM 구조화 결과 항목이 없습니다: {company_code}, 파일: {report_file_path}")

        #print("----- 구조화 직후 결과 -------")
        #pprint(financial_items, indent=4)

        return has_llm_error, financial_items
    
    async def fill_data_missing(self, extracted_tables, financial_items, report_file_path, unit_info):
        logger.info(f"fill_none_items : value")
        #fill_none_items = self.fill_none_items(extracted_tables, financial_items, 'value')
        financial_items = self.fill_none_items(extracted_tables, financial_items, 'value')
        logger.info(f"fill_none_items : cumulative_value")
        #fill_none_items = self.fill_none_items(extracted_tables, financial_items, 'cumulative_value')
        financial_items = self.fill_none_items(extracted_tables, financial_items, 'cumulative_value')

        # 핵심 지표 누락 체크
        financial_items = await self._check_and_add_missing_essential_indicators(financial_items, report_file_path)

        if unit_info == "USD":
            # USD인 경우 평균환율 정보 추출 및 KRW로 변환
            exchange_rate = await self.find_average_exchange_rate(report_file_path)
            if exchange_rate:
                logger.info(f"USD -> KRW 변환 적용: 평균환율 = {exchange_rate}")
                financial_items = await self.convert_usd_to_krw(report_file_path, financial_items)
            else:
                logger.warning(f"USD 단위 데이터이지만 환율 정보를 찾지 못했습니다: {report_file_path}")
                
        return financial_items
    
    async def convert_usd_to_krw(self, report_file_path, financial_items):
        """
        USD 단위의 재무 항목을 KRW로 변환하는 함수

        Args:
            report_file_path: 재무 보고서 파일 경로
            financial_items: 재무 항목 리스트

        Returns:
            환율이 적용된 재무 항목 리스트
        """
        # 평균환율 정보 가져오기
        exchange_rate = await self.find_average_exchange_rate(report_file_path)
        
        if not exchange_rate:
            logger.warning(f"환율 정보를 찾지 못해 USD 단위를 KRW로 변환할 수 없습니다: {report_file_path}")
            return financial_items
        
        logger.info(f"재무 항목 USD -> KRW 변환 시작: 적용 환율 = {exchange_rate}")
        
        # 모든 항목에 환율 적용
        converted_items = []
        for item in financial_items:
            # 항목의 값과 누적값 변환
            values = item.get("values", [])
            for value_info in values:
                # 값과 누적값 변환
                if "value" in value_info and value_info["value"] is not None:
                    value_info["value"] = value_info["value"] * exchange_rate
                
                if "cumulative_value" in value_info and value_info["cumulative_value"] is not None:
                    value_info["cumulative_value"] = value_info["cumulative_value"] * exchange_rate
                
                # 단위를 '원'으로 변경
                value_info["unit"] = "원"
            
            # 변환된 항목 추가
            converted_items.append(item)
        
        logger.info(f"USD -> KRW 변환 완료: {len(converted_items)}개 항목")
        return converted_items

    async def find_average_exchange_rate(self, report_file_path):
        """
        재무에 관한 사항 섹션에서 평균환율 정보를 찾는 함수

        Args:
            report_file_path: 재무 보고서 파일 경로

        Returns:
            평균환율 값 (float), 찾지 못하면 None 반환
        """
        try:
            # 공백과 숫자 제거 함수
            def clean_text(text):
                # 공백 제거 및 소문자 변환
                text = re.sub(r'\s+', '', text.lower())
                # 숫자 및 괄호 제거
                text = re.sub(r'[0-9()]+', '', text)
                return text

            # fitz로 목차 추출
            doc = fitz.open(report_file_path)
            toc = doc.get_toc()
            
            start_page = None
            end_page = None
            
            # '재무에관한사항' 목차 찾기
            for i, item in enumerate(toc):
                level, title, page = item
                clean_title = remove_number_prefix_toc(title)
                #clean_title = remove_comment_number(title)
                
                if '재무에관한사항' in clean_title or '재무에관한' in clean_title:
                    # 시작 페이지 (fitz는 0-based가 아닌 1-based로 목차 페이지 반환)
                    start_page = page - 1
                    
                    # 동일 레벨의 다음 목차를 찾아 종료 페이지 설정
                    for next_item in toc[i+1:]:
                        next_level, next_title, next_page = next_item
                        if next_level <= level:
                            end_page = next_page - 2
                            break
                    
                    # 다음 섹션을 찾지 못한 경우 문서 끝까지 검색
                    if end_page is None:
                        end_page = len(doc) - 1
                    
                    break
            
            # 목차에서 찾지 못한 경우 기본값 설정
            if start_page is None:
                start_page = 0
                end_page = min(30, len(doc) - 1)  # 처음 30페이지만 검색
                logger.warning(f"'재무에관한사항' 목차를 찾지 못해 기본 페이지 범위 설정: {start_page+1}~{end_page+1}")
            else:
                logger.info(f"'재무에관한사항' 섹션 찾음: 페이지 {start_page+1}~{end_page+1}")
            
            # pdfplumber로 테이블 추출
            with pdfplumber.open(report_file_path) as pdf:
                for page_num in range(start_page, end_page + 1):
                    if page_num >= len(pdf.pages):
                        continue
                    
                    page = pdf.pages[page_num]
                    tables = page.extract_tables()
                    
                    # 각 테이블의 행 검사
                    for table in tables:
                        for row in table:
                            # None 값 처리 및 문자열 변환
                            row = [str(cell).strip() if cell is not None else "" for cell in row]
                            
                            # '평균환율' 포함 행 확인
                            if any('평균환율' in cell for cell in row):
                                logger.info(f"평균환율 정보 발견: {row}")
                                
                                # 행에서 환율 정보 찾기 (보통 두 번째 열)
                                if len(row) > 1:
                                    # 숫자만 추출
                                    exchange_rate_str = re.sub(r'[^\d.]', '', row[1])
                                    if exchange_rate_str:
                                        try:
                                            exchange_rate = float(exchange_rate_str)
                                            logger.info(f"평균환율: {exchange_rate}")
                                            return exchange_rate
                                        except ValueError:
                                            logger.warning(f"환율 변환 실패: {exchange_rate_str}")
            
            logger.warning(f"평균환율 정보를 찾지 못했습니다: {report_file_path}")
            return None
        
        except Exception as e:
            logger.error(f"평균환율 추출 중 오류 발생: {e}")
            return None
