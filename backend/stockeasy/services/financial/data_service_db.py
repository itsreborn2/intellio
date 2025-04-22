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

class FinancialDataServiceDB:
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
                "income_statement": ["손익계산서", "포괄손익계산서","연결 손익계산서", "연결손익계산서", "연결포괄손익계산서", "연결 포괄손익계산서"],
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
                                # 다음 섹션 페이지까지.를 끝 페이지로 설정
                                end_page = next_page
                                break
                        
                        # 다음 섹션을 찾지 못한 경우 기본적으로 시작 페이지 + 2로 설정
                        if end_page is None:
                            end_page = min(start_page + 10, len(doc) - 1)
                            
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
                                end_page = min(start_page + 10, len(doc) - 1)  # 기본적으로 3페이지 범위
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
            
            all_text = await self.extract_exact_financial_data(report_file_path, "income_statement", report_type, 
                                                               start_page, end_page+1)
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
            structured_data = await self.llm_service.structure_income_statement_table(report_type, report_year, 
                                                                                      report_quarter,   all_text)
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

            # 코드 점검해야됨. 일진전기 23.1Q 처럼 분기손이익 항목 없음.
            #  하위 항목으로 　지배기업의 소유주에게 귀속되는 분기순이익, 　비지배지분에 귀속되는 분기순이익 합산
            # 핵심 지표 누락 체크 
            essential_codes = ["net_income", "revenue", "operating_income"]
            found_essentials = set(item.get("item_code") for item in financial_items)

            for code in essential_codes:
                found_code_items = []
                if code not in found_essentials:
                    logger.warning(f"핵심 지표 누락: {code}")
                    logger.warning(f"파일: {report_file_path}")
                    # 누락된 항목을 찾기 위한 키워드 목록
                    # keywords = {
                    #     "net_income": ["당기순이익", "분기순이익", "반기순이익", "순이익", "순손익"],
                    #     "revenue": ["매출액", "영업수익", "영업수입", "매출"],
                    #     "operating_income": ["영업이익", "영업손익", "영업손실"]
                    # }
                    keywords = { "net_income" : "당기순이익", 
                                "revenue" : "매출액", 
                                "operating_income" : "영업이익" }

                    # 원본 텍스트에서 유사 항목 찾기 시도
                    #for keyword in keywords[code]:
                    # 키워드를 포함하는 항목 찾기
                    for item in financial_items:
                        if code in item.get("item_code", ""):
                            year = item.get("values")[0].get("year", 0)
                            quarter = item.get("values")[0].get("quarter", 0)
                            logger.warning(f"'{keyword}'가 포함된 항목 발견: {year}년 {quarter}분기 {item.get('item_code')} -> {item.get('item_name')}, {item.get('values')[0].get('value', 0)}")
                            found_code_items.append(item)
                
                if len(found_code_items) > 0:
                    logger.warning(f"핵심 지표 누락 항목 찾음. 병합 시도: {code}, {len(found_code_items)}개 항목")
                    values = 0
                    cumulative_values = 0
                    
                    for item in found_code_items:
                        # 항목의 값 누적.
                        values += item.get("values")[0].get("value", 0)
                        cumulative_values += item.get("values")[0].get("cumulative_value", 0)
                        quarter = item.get("values")[0].get("quarter", 0)
                        unit = item.get("values")[0].get("unit", "")
                        year = item.get("values")[0].get("year", 0)
                    add_item = { "item_code": code, "item_name": keywords[code], 
                                    "values": [ 
                                        { "value": values, "cumulative_value": cumulative_values,
                                         "quarter": quarter, "unit": unit, "year": year
                                         } 
                                        ] }
                    pprint(add_item, indent=4)
                    financial_items.append(add_item)
                    logger.warning(f"병합 결과: {code} = {values}")
                    pprint(financial_items, indent=4)
                    


            
            # 4. 데이터베이스 저장
            logger.info(f"데이터베이스 저장 시작: 회사={company_code}, 보고서={report.id}")
            save_start_time = datetime.now()
            saved_items = await self._save_structured_data(
                company.id, report.id, structured_data, income_statement_keywords
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
    
    async def extract_exact_financial_data(self, report_file_path: str, 
                                           statement_type: str, 
                                           report_type: str, 
                                           start_page: int, end_page: int) -> Dict[str, Any]:
        all_text = ""
        # fitz 대신 pdfplumber 사용하여 텍스트 추출
        logger.info(f"페이지 텍스트 추출 시작: 페이지 {start_page}~{end_page}")
        with pdfplumber.open(report_file_path) as pdf:
            for page_num in range(start_page, end_page):
                #logger.info(f"패아지 : {page_num}")
                if page_num < len(pdf.pages):
                    
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    if text:
                        text = re.sub(r'.*전자공시시스템 dart\.fss\.or\.kr.*(\n|$)', '', text)
                    if text:
                        all_text += text
        
        all_text = self.extract_exact_financial_data_in(all_text, statement_type)

        return all_text
    def extract_exact_financial_data_in(self, text, statement_type):
        """
        텍스트에서 정확히 재무제표 키워드만 있는 라인을 찾아 해당 위치부터 텍스트를 추출합니다.
        """
        # 키워드 목록 (찾고자 하는 재무제표 유형)
        income_statement_keywords = [
            "연결 포괄손익계산서", "연결포괄손익계산서", 
            "연결 손익계산서", "연결손익계산서",
            "포괄손익계산서", "손익계산서"
        ]
        cash_flow_keywords = [
            "연결현금흐름표", "연결 현금흐름표", 
            "별도 현금흐름표", "별도현금흐름표",
            "현금흐름표"
        ]
        balance_sheet_keywords = [
            "연결재무상태표", "연결 재무상태표", 
            "별도 재무상태표", "별도재무상태표",
            "재무상태표"
        ]
        capital_changes_keywords = [
             "연결자본변동표", "연결 자본변동표", 
             "별도 자본변동표", "별도자본변동표",
             "자본변동표"
        ]
        start_keyword = income_statement_keywords
        end_keyword = []

        
       # print(f"end keyword : {end_keyword}")
        #print(text)
        # 라인별로 분리
        lines = text.split('\n')
        start_line = -1
        end_line = len(text)

        
        # 각 라인에 대해 정확히 키워드만 있는지 확인
        b연결 = False
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line in start_keyword:
                start_line = i
                found_keyword_start = stripped_line
                if "연결" in stripped_line:
                    b연결 = True
                break
        logger.info(f"start keyword 발견 : '{found_keyword_start}', 라인 {start_line+1}, 연결={b연결}")

        if statement_type == "income_statement":
            start_keyword = income_statement_keywords
            end_keyword = cash_flow_keywords + balance_sheet_keywords + capital_changes_keywords
        elif statement_type == "cash_flow":
            start_keyword = cash_flow_keywords
            end_keyword = income_statement_keywords + balance_sheet_keywords + capital_changes_keywords
        elif statement_type == "balance_sheet":
            start_keyword = balance_sheet_keywords
            end_keyword = income_statement_keywords + cash_flow_keywords + capital_changes_keywords
        elif statement_type == "capital_changes":
            start_keyword = capital_changes_keywords
            end_keyword = income_statement_keywords + cash_flow_keywords + balance_sheet_keywords

        # 각 라인에 대해 정확히 키워드만 있는지 확인
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line in end_keyword:
                if start_line >= 0 and start_line < i: # start보다 뒤쪽에서 만나야제.
                    end_line = i -1
                    found_keyword_end = stripped_line
                    break
        
        logger.info(f"end keyword 발견 : '{found_keyword_end}', 라인 {end_line}")
        if start_line == -1:
            start_line = 0
        # 해당 라인부터의 텍스트만 반환
        return '\n'.join(lines[start_line:end_line])
    


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
        logger.info(f"current_report : {current_report}")
        if not current_report:
            logger.error(f"보고서를 찾을 수 없습니다: ID={report_id}")
            return saved_items
        
        financial_summary = structured_data.get("financial_summary", None)
        if financial_summary is None:
            logger.error(f"데이터 구조화에 실패했습니다: {company_id}, {report_id}")
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
                logger.error(f"오류 발생 후 중단: {item.get('item_name')}")
                break
                
            item_name = item.get("item_name")
            item_code = item.get("item_code")

            # item_name에서 주석 (주X,Y..) 패턴 제거
            cleaned_item_name = item_name
            if item_name:
                # 정규식을 사용하여 '(주숫자,숫자...)' 패턴 및 앞뒤 공백 제거
                cleaned_item_name = re.sub(r'\s*\(주[\d,]+\)\s*', '', item_name).strip()
                #logger.info(f"cleaned_item_name : {cleaned_item_name}")
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
                    value = value_data.get("value")
                    period_value = value
                    cumulative_value = value_data.get("cumulative_value", None)
                    unit = value_data.get("unit", "원")
                    
                    if value is None:
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
                        
                        if prev_data and prev_data.cumulative_value is not None:
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
                        statement_type, category, cleaned_item_name
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
        elif "포괄손익계산서" in category:
            # 포괄손익계산서 테이블에 저장 (손익계산서 테이블과 동일)
            logger.info(f"포괄손익계산서 항목 저장: {item_name}, 값={value} {unit}")
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
            
        elif "손익계산서" in category:
            # 손익계산서 테이블에 저장
            logger.info(f"손익계산서 항목 저장: {item_name}, 값={value} {unit}")
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

