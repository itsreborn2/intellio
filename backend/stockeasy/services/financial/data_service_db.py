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

from typing import Dict, List, Any, Optional, Tuple, Union

from google.cloud import storage
from common.services.storage import GoogleCloudStorageService
from common.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession


from common.core.database import get_db, get_db_async, get_db_session

from stockeasy.services.financial.pdf_extractor import FinancialPDFExtractor
from stockeasy.services.llm_service import FinancialLLMService
from stockeasy.utils.cache_util import FinancialCacheUtil, cached
from sqlalchemy import select, and_, func
from stockeasy.models.financial_reports import FinancialReport
from stockeasy.models.income_statement_data import IncomeStatementData
from stockeasy.models.balance_sheet_data import BalanceSheetData
from stockeasy.models.cash_flow_data import CashFlowData
from stockeasy.models.equity_change_data import EquityChangeData
from stockeasy.utils.cache_util import FinancialCacheUtil, cached
from sqlalchemy import select, and_, func
from stockeasy.models.financial_data import SummaryFinancialData, FinancialItemMapping

from stockeasy.models.income_statement_data import IncomeStatementData


# # PDF 관련 모든 경고 메시지 숨기기
# warnings.filterwarnings('ignore', category=UserWarning, module='pdfminer')
# warnings.filterwarnings('ignore', category=UserWarning, module='pdfplumber')

# # 로깅 설정
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),  # 콘솔 출력용 핸들러
#     ]
# )
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정
# logging.getLogger("pdfminer").setLevel(logging.ERROR)

class FinancialDataServiceDB:
    """재무 데이터 서비스 클래스"""
    
    def __init__(self, db_session: AsyncSession = None):
        """서비스 초기화"""
        self._db = db_session
        
        # 로거 초기화 메시지 출력
        logger.info("FinancialDataServiceDB 초기화 중...")
        
        self.storage_service = GoogleCloudStorageService(
            project_id=settings.GOOGLE_CLOUD_PROJECT,
            bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
            credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        
        
        logger.info("FinancialDataService 초기화 완료")
        
    async def _get_db_session(self):
        """
        데이터베이스 세션 컨텍스트 매니저
        세션 사용 후 자동으로 정리됩니다.
        """
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def session_context():
            db = await get_db_session()
            try:
                yield db
            finally:
                await db.close()
                logger.debug("DB 세션 정리 완료")
        
        return session_context()
    

    
    async def get_financial_data(self, stock_code: str, date_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """
        주어진 종목 코드에 대한 재무 데이터를 가져옵니다.
        
        Args:
            stock_code: 종목 코드
            date_range: 데이터를 가져올 날짜 범위 (start_date, end_date)
            
        Returns:
            재무 데이터를 포함하는 딕셔너리
        """
        async with await self._get_db_session() as db:
            try:
                # 날짜 범위가 제공되지 않은 경우 기본값 설정 (최근 2년)
                if not date_range:
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=1.4*365)  # 5개 분기
                else:
                    start_date = date_range.get("start_date")
                    end_date = date_range.get("end_date")
                
                # 날짜 범위를 YYYYMM 형식으로 변환
                start_year_month = int(start_date.strftime('%Y%m'))
                end_year_month = int(end_date.strftime('%Y%m'))
                
                logger.info(f"재무 데이터 조회: {stock_code}, 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
                
                # 해당 종목의 분기 데이터 확인
                query_quarters = select(IncomeStatementData.year_month)\
                    .join(IncomeStatementData.company)\
                    .where(
                        and_(
                            IncomeStatementData.company.has(company_code=stock_code),
                            IncomeStatementData.year_month.between(start_year_month, end_year_month)
                        )
                    )\
                    .distinct()\
                    .order_by(IncomeStatementData.year_month.desc())
                
                quarters_result = await db.execute(query_quarters)
                available_quarters = [row[0] for row in quarters_result.all()]
                
                # 최소 5개 분기 확인
                if len(available_quarters) < 5:
                    # 더 많은 데이터가 필요한 경우 범위 확장
                    extended_start_year_month = start_year_month - (100 * (5 - len(available_quarters)))
                    
                    # 확장된 쿼리 실행
                    query_extended = select(IncomeStatementData.year_month)\
                        .join(IncomeStatementData.company)\
                        .where(
                            and_(
                                IncomeStatementData.company.has(company_code=stock_code),
                                IncomeStatementData.year_month.between(extended_start_year_month, end_year_month)
                            )
                        )\
                        .distinct()\
                        .order_by(IncomeStatementData.year_month.desc())
                    
                    extended_result = await db.execute(query_extended)
                    available_quarters = [row[0] for row in extended_result.all()]
                    
                    # 시작 날짜 업데이트
                    if available_quarters:
                        start_year_month = min(available_quarters)
                
                # 사용 가능한 분기가 여전히 5개 미만이면 경고 로그 출력
                if len(available_quarters) < 5:
                    logger.warning(f"종목 {stock_code}에 대해 5개 미만의 분기 데이터만 사용 가능합니다: {len(available_quarters)}개")
                
                # 매출, 영업이익, 순이익 데이터 조회
                query = select(
                    IncomeStatementData.year_month,
                    IncomeStatementData.period_value,
                    IncomeStatementData.cumulative_value,
                    IncomeStatementData.display_unit,
                    FinancialItemMapping.item_code
                )\
                .join(IncomeStatementData.company)\
                .join(IncomeStatementData.item)\
                .where(
                    and_(
                        IncomeStatementData.company.has(company_code=stock_code),
                        IncomeStatementData.year_month.between(start_year_month, end_year_month),
                        FinancialItemMapping.item_code.in_(["revenue", "operating_income", "net_income"])
                    )
                )\
                .order_by(IncomeStatementData.year_month.desc())
                
                result = await db.execute(query)
                records = result.fetchall()
                logger.info(f"조회된 레코드 개수: {len(records)}")
                
                # 결과 구조화
                financial_data = {
                    "stock_code": stock_code,
                    "period": {
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "quarters": {}
                }
                
                for record in records:
                    year_month, period_value, cumulative_value, display_unit, item_code = record
                    
                    # 분기 데이터가 없으면 초기화
                    if year_month not in financial_data["quarters"]:
                        financial_data["quarters"][year_month] = {}
                    
                    # 항목별 데이터 저장
                    financial_data["quarters"][year_month][item_code] = {
                        "period_value": float(period_value) if period_value is not None else None,
                        "cumulative_value": float(cumulative_value) if cumulative_value is not None else None,
                        "display_unit": display_unit
                    }
                
                # 분기 정렬 (최신 분기부터)
                sorted_quarters = sorted(financial_data["quarters"].keys(), reverse=True)
                sorted_data = {q: financial_data["quarters"][q] for q in sorted_quarters}
                financial_data["quarters"] = sorted_data
                
                return financial_data
            except Exception as e:
                logger.exception(f"재무 데이터 조회 중 오류: {str(e)}")
                return {}
    
    async def get_financial_data_with_qoq(self, stock_code: str, date_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """
        주어진 종목 코드에 대한 재무 데이터와 전분기 및 전년 동기 대비 성장률을 가져옵니다.
        
        Args:
            stock_code: 종목 코드
            date_range: 데이터를 가져올 날짜 범위 (start_date, end_date)
            
        Returns:
            재무 데이터와 성장률을 포함하는 딕셔너리
        """
        async with await self._get_db_session() as db:
            try:
                # 날짜 범위가 제공되지 않은 경우 기본값 설정 (5개 분기)
                if not date_range:
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=1.4*365)  # 5개 분기
                else:
                    start_date = date_range.get("start_date")
                    end_date = date_range.get("end_date")
                
                # 날짜 범위를 YYYYMM 형식으로 변환
                start_year_month = int(start_date.strftime('%Y%m'))
                end_year_month = int(end_date.strftime('%Y%m'))
                
                logger.info(f"재무 데이터(성장률 포함) 조회: {stock_code}, 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
                
                # 확장된 기간 설정 (YoY 계산을 위해 1년 추가)
                extended_start_year_month = start_year_month - 100
                
                # 직접 SQL 쿼리로 QoQ, YoY 계산 (sqlalchemy.text 사용)
                from sqlalchemy import text
                
                sql_query = text("""
                WITH quarterly_data AS (
                    SELECT
                        c.company_name AS company_name,
                        c.company_code AS company_code,
                        fim.standard_name AS item_name,
                        fim.item_code,
                        isd.year_month,
                        CASE 
                            WHEN isd.year_month % 100 = 3 THEN 1
                            WHEN isd.year_month % 100 = 6 THEN 2
                            WHEN isd.year_month % 100 = 9 THEN 3
                            WHEN isd.year_month % 100 = 12 THEN 4
                        END AS quarter,
                        CAST(isd.year_month / 100 AS INT) AS year,
                        CAST(CASE
                            WHEN isd.display_unit = '원' THEN CAST(isd.period_value AS FLOAT) / 100000000.0
                            WHEN isd.display_unit = '천원' THEN CAST(isd.period_value AS FLOAT) / 100000.0
                            WHEN isd.display_unit = '백만원' THEN CAST(isd.period_value AS FLOAT) / 100.0
                            WHEN isd.display_unit = '십억원' THEN CAST(isd.period_value AS FLOAT) / 10.0
                            WHEN isd.display_unit = '억원' THEN CAST(isd.period_value AS FLOAT)
                            ELSE CAST(isd.period_value AS FLOAT)
                        END AS NUMERIC(20,2)) AS period_value,
                        CAST(CASE
                            WHEN isd.display_unit = '원' THEN CAST(isd.cumulative_value AS FLOAT) / 100000000.0
                            WHEN isd.display_unit = '천원' THEN CAST(isd.cumulative_value AS FLOAT) / 100000.0
                            WHEN isd.display_unit = '백만원' THEN CAST(isd.cumulative_value AS FLOAT) / 100.0
                            WHEN isd.display_unit = '십억원' THEN CAST(isd.cumulative_value AS FLOAT) / 10.0
                            WHEN isd.display_unit = '억원' THEN CAST(isd.cumulative_value AS FLOAT)
                            ELSE CAST(isd.cumulative_value AS FLOAT)
                        END AS NUMERIC(20,2)) AS cumulative_value,
                        '억원' AS display_unit
                    FROM
                        stockeasy.income_statement_data isd
                    JOIN
                        stockeasy.financial_item_mappings fim ON isd.item_id = fim.id
                    JOIN
                        stockeasy.companies c ON isd.company_id = c.id
                    WHERE
                        c.company_code = :stock_code AND
                        isd.year_month BETWEEN :extended_start_ym AND :end_ym AND
                        fim.item_code IN ('revenue', 'operating_income', 'net_income')
                ),
                -- 전년 동기 데이터를 위한 서브쿼리 추가
                prev_year_data AS (
                    SELECT 
                        q1.item_code,
                        q1.quarter,
                        q1.year,
                        q1.period_value AS current_value,
                        q2.period_value AS prev_year_value
                    FROM quarterly_data q1
                    LEFT JOIN quarterly_data q2 
                        ON q1.item_code = q2.item_code 
                        AND q1.quarter = q2.quarter 
                        AND q1.year = q2.year + 1
                )
                SELECT 
                    qd.company_name,
                    qd.company_code,
                    qd.item_name,
                    qd.item_code,
                    qd.year_month,
                    qd.quarter,
                    qd.year,
                    qd.period_value,
                    qd.cumulative_value,
                    qd.display_unit,
                    CASE 
                        WHEN LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter) IS NULL THEN NULL
                        -- 이전 분기 음수, 현재 분기 양수 -> 항상 양수로 표시 (개선)
                        WHEN LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter) < 0 
                            AND qd.period_value > 0 THEN 
                            CAST((qd.period_value - LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter)) * 100.0 / 
                                ABS(NULLIF(LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter), 0)) AS NUMERIC(20,2))
                        -- 이전 분기 양수, 현재 분기 음수 -> 항상 음수로 표시 (악화)
                        WHEN LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter) > 0 
                            AND qd.period_value < 0 THEN 
                            -1 * CAST((ABS(qd.period_value) + LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter)) * 100.0 / 
                                ABS(NULLIF(LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter), 0)) AS NUMERIC(20,2))
                        -- 둘 다 같은 부호일 경우 일반적인 계산
                        ELSE CAST((qd.period_value - LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter)) * 100.0 / 
                            ABS(NULLIF(LAG(qd.period_value) OVER (PARTITION BY qd.item_code ORDER BY qd.year, qd.quarter), 0)) AS NUMERIC(20,2))
                    END AS qoq,
                    (
                        SELECT 
                            CASE 
                                WHEN pyd.prev_year_value IS NULL THEN NULL
                                -- 이전 년도 음수, 현재 년도 양수 -> 항상 양수로 표시 (개선)
                                WHEN pyd.prev_year_value < 0 AND pyd.current_value > 0 THEN 
                                    CAST((pyd.current_value - pyd.prev_year_value) * 100.0 / 
                                        ABS(NULLIF(pyd.prev_year_value, 0)) AS NUMERIC(20,2))
                                -- 이전 년도 양수, 현재 년도 음수 -> 항상 음수로 표시 (악화)
                                WHEN pyd.prev_year_value > 0 AND pyd.current_value < 0 THEN 
                                    -1 * CAST((ABS(pyd.current_value) + pyd.prev_year_value) * 100.0 / 
                                        ABS(NULLIF(pyd.prev_year_value, 0)) AS NUMERIC(20,2))
                                -- 둘 다 같은 부호일 경우 일반적인 계산
                                ELSE CAST((pyd.current_value - pyd.prev_year_value) * 100.0 / 
                                    ABS(NULLIF(pyd.prev_year_value, 0)) AS NUMERIC(20,2))
                            END
                        FROM prev_year_data pyd
                        WHERE pyd.item_code = qd.item_code AND pyd.year = qd.year AND pyd.quarter = qd.quarter
                    ) AS yoy
                FROM 
                    quarterly_data qd
                WHERE
                    qd.year_month BETWEEN :start_ym AND :end_ym
                ORDER BY
                    qd.item_code, qd.year DESC, qd.quarter DESC
            """)
                
                # 쿼리 매개변수
                params = {
                    "stock_code": stock_code,
                    "start_ym": start_year_month,
                    "end_ym": end_year_month,
                    "extended_start_ym": extended_start_year_month
                }
                
                # 쿼리 실행
                result = await db.execute(sql_query, params)
                records = result.fetchall()
                logger.info(f"조회된 레코드 개수: {len(records)}")
                
                # 결과 구조화
                financial_data = {
                    "stock_code": stock_code,
                    "period": {
                        "start_date": start_date.strftime('%Y-%m-%d'),
                        "end_date": end_date.strftime('%Y-%m-%d')
                    },
                    "quarters": {}
                }
                
                for record in records:
                    company_name = record.company_name
                    company_code = record.company_code
                    item_name = record.item_name
                    item_code = record.item_code
                    year_month = record.year_month
                    quarter = record.quarter
                    year = record.year
                    period_value = record.period_value
                    cumulative_value = record.cumulative_value
                    display_unit = record.display_unit
                    qoq = record.qoq
                    yoy = record.yoy
                    
                    # 분기 데이터가 없으면 초기화
                    if year_month not in financial_data["quarters"]:
                        financial_data["quarters"][year_month] = {
                            "year": year,
                            "quarter": quarter
                        }
                    
                    # 항목별 데이터 저장
                    financial_data["quarters"][year_month][item_code] = {
                        "standard_name": item_name,
                        "period_value": float(period_value) if period_value is not None else None,
                        "cumulative_value": float(cumulative_value) if cumulative_value is not None else None,
                        "display_unit": display_unit,
                        "qoq": float(qoq) if qoq is not None else None,
                        "yoy": float(yoy) if yoy is not None else None
                    }
                
                # 분기 정렬 (최신 분기부터)
                sorted_quarters = sorted(financial_data["quarters"].keys(), reverse=True)
                sorted_data = {q: financial_data["quarters"][q] for q in sorted_quarters}
                financial_data["quarters"] = sorted_data
                
                return financial_data
            except Exception as e:
                logger.exception(f"재무 데이터 성장률 조회 중 오류: {str(e)}")
                return {}
