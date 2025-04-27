from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any, Optional, Tuple, Union
import logging
from decimal import Decimal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.future import select
import sqlalchemy.exc

from stockeasy.models.companies import Company
from stockeasy.models.financial_reports import FinancialReport
from stockeasy.models.financial_data import (
    FinancialItemMapping, 
    FinancialItemRawMapping,
    SummaryFinancialData,
)
from stockeasy.models.income_statement_data import IncomeStatementData
from stockeasy.models.balance_sheet_data import BalanceSheetData
from stockeasy.models.cash_flow_data import CashFlowData
from stockeasy.models.equity_change_data import EquityChangeData

logger = logging.getLogger(__name__)


class FinancialRepository:
    """
    재무 데이터 관련 저장소 클래스
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    # 회사 관련 메서드
    async def get_company_by_code(self, company_code: str) -> Optional[Company]:
        """회사 코드로 회사 정보 조회"""
        result = await self.db.execute(
            select(Company).where(Company.company_code == company_code)
        )
        return result.scalar_one_or_none()
    
    # 보고서 관련 메서드
    async def get_or_create_financial_report(
        self, company_id: int, report_type: str, report_year: int, 
        report_quarter: Optional[int], file_path: Optional[str] = None
    ) -> FinancialReport:
        """보고서 정보 조회 또는 생성"""
        year_month = report_year * 100 + (report_quarter * 3 if report_quarter else 12)
        
        result = await self.db.execute(
            select(FinancialReport).where(
                and_(
                    FinancialReport.company_id == company_id,
                    FinancialReport.report_year == report_year,
                    FinancialReport.report_quarter == report_quarter
                )
            )
        )
        report = result.scalar_one_or_none()
        
        if not report:
            report = FinancialReport(
                company_id=company_id,
                report_type=report_type,
                report_year=report_year,
                report_quarter=report_quarter,
                year_month=year_month,
                file_path=file_path,
                processed=False
            )
            self.db.add(report)
            await self.db.flush()
        elif file_path and not report.file_path:
            report.file_path = file_path
            
        return report
    
    # 항목 매핑 관련 메서드
    async def get_item_mapping_by_code(self, item_code: str) -> Optional[FinancialItemMapping]:
        """항목 코드로 항목 매핑 조회"""
        stmt = select(FinancialItemMapping).where(FinancialItemMapping.item_code == item_code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_item_mapping_by_raw_name(self, raw_name: str) -> Optional[FinancialItemMapping]:
        """원본 항목명으로 항목 매핑 조회"""
        result = await self.db.execute(
            select(FinancialItemMapping)
            .join(FinancialItemRawMapping, FinancialItemMapping.id == FinancialItemRawMapping.mapping_id)
            .where(FinancialItemRawMapping.raw_name == raw_name)
        )
        return result.scalar_one_or_none()
    
    async def create_item_mapping(
        self, item_code: str, category: str, standard_name: str,
        description: Optional[str] = None, display_order: Optional[int] = None
    ) -> FinancialItemMapping:
        """
        항목 매핑 생성. item_code가 이미 존재하면 아무 작업도 하지 않고
        기존 또는 새로 생성된 매핑 객체를 반환합니다.
        """
        insert_stmt = insert(FinancialItemMapping).values(
            item_code=item_code,
            category=category,
            standard_name=standard_name,
            description=description,
            display_order=display_order,
            is_active=True
        ).on_conflict_do_nothing(
            index_elements=['item_code']
        )

        # ON CONFLICT DO NOTHING 실행
        await self.db.execute(insert_stmt)

        # 삽입되었거나 기존에 있던 매핑 객체를 조회하여 반환
        item_mapping = await self.get_item_mapping_by_code(item_code)

        if item_mapping is None:
            logger.error(f"매핑 생성 또는 조회 실패: {item_code}")
            raise Exception(f"Failed to create or find item mapping for code: {item_code}")

        return item_mapping
    
    async def create_raw_mapping(self, mapping_id: int, raw_name: str) -> FinancialItemRawMapping:
        """원본 항목명 매핑 생성"""
        # 이미 존재하는지 확인
        result = await self.db.execute(
            select(FinancialItemRawMapping).where(
                and_(
                    FinancialItemRawMapping.mapping_id == mapping_id,
                    FinancialItemRawMapping.raw_name == raw_name
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return existing
            
        raw_mapping = FinancialItemRawMapping(
            mapping_id=mapping_id,
            raw_name=raw_name
        )
        self.db.add(raw_mapping)
        await self.db.flush()
        return raw_mapping
    
    # 요약재무정보 관련 메서드
    async def save_summary_financial_data(
        self, report_id: int, company_id: int, item_id: int, year_month: int, 
        value: Union[Decimal, float], display_unit: str,
        cumulative_value: Optional[Union[Decimal, float]] = None,
        period_value: Optional[Union[Decimal, float]] = None,
        is_cumulative: bool = False,
        statement_type: Optional[str] = None
    ) -> SummaryFinancialData:
        """요약재무정보 저장"""
        # 이미 존재하는지 확인
        result = await self.db.execute(
            select(SummaryFinancialData).where(
                and_(
                    SummaryFinancialData.report_id == report_id,
                    SummaryFinancialData.company_id == company_id,
                    SummaryFinancialData.item_id == item_id,
                    SummaryFinancialData.year_month == year_month
                )
            )
        )
        data = result.scalar_one_or_none()
        
        # 기본값 설정
        if cumulative_value is None:
            cumulative_value = value
        if period_value is None:
            period_value = value
        
        if data:
            # 기존 데이터 업데이트
            data.value = value
            data.display_unit = display_unit
            data.cumulative_value = cumulative_value
            data.period_value = period_value
            data.is_cumulative = is_cumulative
            data.statement_type = statement_type
        else:
            # 새 데이터 생성
            data = SummaryFinancialData(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=display_unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative,
                statement_type=statement_type
            )
            self.db.add(data)
            
        await self.db.flush()
        return data
    
    async def get_summary_financial_data(
        self, company_code: Optional[str] = None, 
        item_codes: Optional[List[str]] = None,
        start_year_month: Optional[int] = None,
        end_year_month: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """요약재무정보 조회"""
        # 기본 쿼리 구성
        query = (
            select(
                Company.company_code,
                Company.company_name,
                FinancialItemMapping.item_code,
                FinancialItemMapping.standard_name,
                SummaryFinancialData.year_month,
                SummaryFinancialData.value,
                SummaryFinancialData.display_unit
            )
            .join(Company, SummaryFinancialData.company_id == Company.id)
            .join(FinancialItemMapping, SummaryFinancialData.item_id == FinancialItemMapping.id)
        )
        
        # 조건 추가
        conditions = []
        
        if company_code:
            conditions.append(Company.company_code == company_code)
            
        if item_codes:
            conditions.append(FinancialItemMapping.item_code.in_(item_codes))
            
        if start_year_month:
            conditions.append(SummaryFinancialData.year_month >= start_year_month)
            
        if end_year_month:
            conditions.append(SummaryFinancialData.year_month <= end_year_month)
            
        if conditions:
            query = query.where(and_(*conditions))
            
        # 정렬 추가 (기본: 회사 코드, 항목 코드, 연월 내림차순)
        query = query.order_by(
            Company.company_code,
            FinancialItemMapping.item_code,
            desc(SummaryFinancialData.year_month)
        )
        
        # 전체 개수 조회
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await self.db.scalar(count_query)
        
        # 페이지네이션 적용
        query = query.limit(limit).offset(offset)
        
        # 쿼리 실행
        result = await self.db.execute(query)
        rows = result.all()
        
        # 결과 가공
        data = []
        for row in rows:
            data.append({
                "company_code": row.company_code,
                "company_name": row.company_name,
                "item_code": row.item_code,
                "item_name": row.standard_name,
                "year_month": row.year_month,
                "value": row.value,
                "display_unit": row.display_unit
            })
            
        return data, total_count
    
    async def save_income_statement_data(
        self, report_id: int, company_id: int, item_id: int, year_month: int, 
        value: Union[Decimal, float], display_unit: str,
        statement_type: str,
        cumulative_value: Optional[Union[Decimal, float]] = None,
        period_value: Optional[Union[Decimal, float]] = None,
        is_cumulative: bool = True,
        
    ) -> IncomeStatementData:
        """손익계산서 데이터 저장"""
        try:
            # 이미 존재하는지 확인
            result = await self.db.execute(
                select(IncomeStatementData).where(
                    and_(
                        IncomeStatementData.report_id == report_id,
                        IncomeStatementData.company_id == company_id,
                        IncomeStatementData.item_id == item_id,
                        IncomeStatementData.year_month == year_month
                    )
                )
            )
            data = result.scalar_one_or_none()
            
            # 기본값 설정
            if cumulative_value is None:
                cumulative_value = value
            if period_value is None:
                period_value = value
            
            if data:
                # 기존 데이터 업데이트
                data.value = value
                data.display_unit = display_unit
                data.cumulative_value = cumulative_value
                data.period_value = period_value
                data.is_cumulative = is_cumulative
                data.statement_type = statement_type
                try:
                    await self.db.flush()
                except Exception as e:
                    logger.error(f"손익계산서 데이터 업데이트 중 오류 발생: {e}")
                    await self.db.rollback()
                    raise
            else:
                try:
                    # 새 데이터 생성
                    data = IncomeStatementData(
                        report_id=report_id,
                        company_id=company_id,
                        item_id=item_id,
                        year_month=year_month,
                        value=value,
                        display_unit=display_unit,
                        cumulative_value=cumulative_value,
                        period_value=period_value,
                        is_cumulative=is_cumulative,
                        statement_type=statement_type
                    )
                    self.db.add(data)
                    await self.db.flush()
                except sqlalchemy.exc.IntegrityError as e:
                    # 중복 키 에러 발생 시 데이터 조회 후 업데이트
                    await self.db.rollback()
                    logger.warning(f"중복 키 제약 조건 발생. 기존 데이터를 업데이트합니다: {e}")
                    
                    # 다시 데이터 조회
                    result = await self.db.execute(
                        select(IncomeStatementData).where(
                            and_(
                                IncomeStatementData.report_id == report_id,
                                IncomeStatementData.company_id == company_id,
                                IncomeStatementData.item_id == item_id,
                                IncomeStatementData.year_month == year_month
                            )
                        )
                    )
                    data = result.scalar_one_or_none()
                    
                    if data:
                        # 기존 데이터 업데이트
                        data.value = value
                        data.display_unit = display_unit
                        data.cumulative_value = cumulative_value
                        data.period_value = period_value
                        data.is_cumulative = is_cumulative
                        data.statement_type = statement_type
                        await self.db.flush()
                    else:
                        # 여전히 없다면 다른 문제이므로 예외 발생
                        logger.error(f"데이터 저장 중 알 수 없는 오류 발생: {e}")
                        raise
        except Exception as e:
            logger.error(f"손익계산서 데이터 저장 중 오류 발생: {e}")
            raise
            
        return data
    
    async def save_balance_sheet_data(
        self, report_id: int, company_id: int, item_id: int, year_month: int, 
        value: Union[Decimal, float], display_unit: str,
        cumulative_value: Optional[Union[Decimal, float]] = None,
        period_value: Optional[Union[Decimal, float]] = None,
        is_cumulative: bool = False
    ) -> BalanceSheetData:
        """재무상태표 데이터 저장"""
        # 이미 존재하는지 확인
        result = await self.db.execute(
            select(BalanceSheetData).where(
                and_(
                    BalanceSheetData.report_id == report_id,
                    BalanceSheetData.company_id == company_id,
                    BalanceSheetData.item_id == item_id,
                    BalanceSheetData.year_month == year_month
                )
            )
        )
        data = result.scalar_one_or_none()
        
        # 기본값 설정
        if cumulative_value is None:
            cumulative_value = value
        if period_value is None:
            period_value = value
        
        if data:
            # 기존 데이터 업데이트
            data.value = value
            data.display_unit = display_unit
            data.cumulative_value = cumulative_value
            data.period_value = period_value
            data.is_cumulative = is_cumulative
        else:
            # 새 데이터 생성
            data = BalanceSheetData(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=display_unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative
            )
            self.db.add(data)
            
        await self.db.flush()
        return data
        
    async def save_cash_flow_data(
        self, report_id: int, company_id: int, item_id: int, year_month: int, 
        value: Union[Decimal, float], display_unit: str,
        cumulative_value: Optional[Union[Decimal, float]] = None,
        period_value: Optional[Union[Decimal, float]] = None,
        is_cumulative: bool = True
    ) -> CashFlowData:
        """현금흐름표 데이터 저장"""
        # 이미 존재하는지 확인
        result = await self.db.execute(
            select(CashFlowData).where(
                and_(
                    CashFlowData.report_id == report_id,
                    CashFlowData.company_id == company_id,
                    CashFlowData.item_id == item_id,
                    CashFlowData.year_month == year_month
                )
            )
        )
        data = result.scalar_one_or_none()
        
        # 기본값 설정
        if cumulative_value is None:
            cumulative_value = value
        if period_value is None:
            period_value = value
        
        if data:
            # 기존 데이터 업데이트
            data.value = value
            data.display_unit = display_unit
            data.cumulative_value = cumulative_value
            data.period_value = period_value
            data.is_cumulative = is_cumulative
        else:
            # 새 데이터 생성
            data = CashFlowData(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=display_unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative
            )
            self.db.add(data)
            
        await self.db.flush()
        return data
        
    async def save_equity_change_data(
        self, report_id: int, company_id: int, item_id: int, year_month: int, 
        value: Union[Decimal, float], display_unit: str,
        cumulative_value: Optional[Union[Decimal, float]] = None,
        period_value: Optional[Union[Decimal, float]] = None,
        is_cumulative: bool = False
    ) -> EquityChangeData:
        """자본변동표 데이터 저장"""
        # 이미 존재하는지 확인
        result = await self.db.execute(
            select(EquityChangeData).where(
                and_(
                    EquityChangeData.report_id == report_id,
                    EquityChangeData.company_id == company_id,
                    EquityChangeData.item_id == item_id,
                    EquityChangeData.year_month == year_month
                )
            )
        )
        data = result.scalar_one_or_none()
        
        # 기본값 설정
        if cumulative_value is None:
            cumulative_value = value
        if period_value is None:
            period_value = value
        
        if data:
            # 기존 데이터 업데이트
            data.value = value
            data.display_unit = display_unit
            data.cumulative_value = cumulative_value
            data.period_value = period_value
            data.is_cumulative = is_cumulative
        else:
            # 새 데이터 생성
            data = EquityChangeData(
                report_id=report_id,
                company_id=company_id,
                item_id=item_id,
                year_month=year_month,
                value=value,
                display_unit=display_unit,
                cumulative_value=cumulative_value,
                period_value=period_value,
                is_cumulative=is_cumulative
            )
            self.db.add(data)
            
        await self.db.flush()
        return data
    
    async def compare_income_statement_data(
        self, report_id: int, company_id: int, item_id: int, year_month: int, 
        value: Union[Decimal, float], display_unit: str,
        statement_type: str,
        cumulative_value: Optional[Union[Decimal, float]] = None,
        period_value: Optional[Union[Decimal, float]] = None,
        is_cumulative: bool = True,
        
    ) -> Dict[str, Any]:
        """
        손익계산서 데이터를 DB의 기존 값과 비교
        
        Returns:
            Dict[str, Any]: 비교 결과 정보
            {
                "exists": bool, # DB에 데이터 존재 여부
                "matches": bool, # 모든 값이 일치하는지 여부
                "differences": Dict[str, Dict[str, Any]] # 일치하지 않는 항목과 그 값 비교
            }
        """
        # 기본값 설정
        if cumulative_value is None:
            cumulative_value = value
        if period_value is None:
            period_value = value
            
        # 이미 존재하는지 확인
        result = await self.db.execute(
            select(IncomeStatementData).where(
                and_(
                    IncomeStatementData.report_id == report_id,
                    IncomeStatementData.company_id == company_id,
                    IncomeStatementData.item_id == item_id,
                    IncomeStatementData.year_month == year_month
                )
            )
        )
        db_data = result.scalar_one_or_none()
        
        # 비교 결과 초기화
        comparison_result = {
            "exists": db_data is not None,
            "matches": True,
            "differences": {}
        }
        
        if not db_data:
            # DB에 데이터가 없는 경우
            comparison_result["matches"] = False
            comparison_result["differences"] = {
                "value": {"expected": value, "actual": None},
                "display_unit": {"expected": display_unit, "actual": None},
                "cumulative_value": {"expected": cumulative_value, "actual": None},
                "period_value": {"expected": period_value, "actual": None},
                "is_cumulative": {"expected": is_cumulative, "actual": None},
                "statement_type": {"expected": statement_type, "actual": None}
            }
            return comparison_result
        
        # 각 필드 비교
        # Decimal 타입의 경우 정확한 비교를 위해 float로 변환
        db_value = float(db_data.value) if db_data.value else None
        db_cumulative = float(db_data.cumulative_value) if db_data.cumulative_value else None
        db_period = float(db_data.period_value) if db_data.period_value else None
        
        # 값 비교 및 차이점 기록
        if db_value != float(value):
            comparison_result["matches"] = False
            comparison_result["differences"]["value"] = {"expected": value, "actual": db_value}
            
        if db_data.display_unit != display_unit:
            comparison_result["matches"] = False
            comparison_result["differences"]["display_unit"] = {"expected": display_unit, "actual": db_data.display_unit}
            
        if db_cumulative != float(cumulative_value):
            comparison_result["matches"] = False
            comparison_result["differences"]["cumulative_value"] = {"expected": cumulative_value, "actual": db_cumulative}
            
        if db_period != float(period_value):
            comparison_result["matches"] = False
            comparison_result["differences"]["period_value"] = {"expected": period_value, "actual": db_period}
            
        if db_data.is_cumulative != is_cumulative:
            comparison_result["matches"] = False
            comparison_result["differences"]["is_cumulative"] = {"expected": is_cumulative, "actual": db_data.is_cumulative}
            
        if db_data.statement_type != statement_type:
            comparison_result["matches"] = False
            comparison_result["differences"]["statement_type"] = {"expected": statement_type, "actual": db_data.statement_type}
        
        return comparison_result