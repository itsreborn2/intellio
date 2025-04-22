from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from common.core.database import get_db
from stockeasy.services.financial.data_service import FinancialDataServicePDF
from stockeasy.schemas.financial_data_schema import (
    ProcessFinancialReportRequest,
    FinancialDataQueryParams
)

router = APIRouter(prefix="/financial", tags=["재무 데이터"])


@router.post("/summary/process")
async def process_financial_summary(
    request: ProcessFinancialReportRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    요약재무정보 처리 API
    
    사업보고서, 반기보고서, 분기보고서에서 요약재무정보를 추출하여 DB에 저장합니다.
    
    - **company_code**: 회사 코드
    - **report_file_path**: 보고서 파일 경로
    - **report_type**: 보고서 유형 (annual, semi, quarter)
    - **report_year**: 보고서 연도
    - **report_quarter**: 보고서 분기 (null, 1, 2, 3, 4)
    """
    service = FinancialDataServicePDF(db)
    result = await service.process_financial_summary(
        company_code=request.company_code,
        report_file_path=request.report_file_path,
        report_type=request.report_type,
        report_year=request.report_year,
        report_quarter=request.report_quarter
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
        
    return result


@router.get("/summary")
async def get_summary_financial_data(
    company_code: Optional[str] = None,
    item_codes: Optional[List[str]] = Query(None),
    start_year_month: Optional[int] = None,
    end_year_month: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    요약재무정보 조회 API
    
    조건에 맞는 요약재무정보를 조회합니다.
    
    - **company_code**: 회사 코드 (선택)
    - **item_codes**: 항목 코드 목록 (선택)
    - **start_year_month**: 시작 연월 (YYYYMM 형식, 선택)
    - **end_year_month**: 종료 연월 (YYYYMM 형식, 선택)
    - **limit**: 최대 조회 개수 (기본값: 100)
    - **offset**: 조회 시작 위치 (기본값: 0)
    """
    service = FinancialDataServicePDF(db)
    result = await service.get_summary_financial_data(
        company_code=company_code,
        item_codes=item_codes,
        start_year_month=start_year_month,
        end_year_month=end_year_month,
        limit=limit,
        offset=offset
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
        
    return result


@router.get("/summary/{company_code}")
async def get_company_financial_summary(
    company_code: str,
    item_codes: Optional[List[str]] = Query(None),
    latest_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    회사별 요약재무정보 조회 API
    
    특정 회사의 요약재무정보를 조회합니다.
    
    - **company_code**: 회사 코드
    - **item_codes**: 항목 코드 목록 (선택)
    - **latest_only**: 최신 데이터만 조회 여부 (기본값: false)
    """
    service = FinancialDataServicePDF(db)
    result = await service.get_company_financial_summary(
        company_code=company_code,
        item_codes=item_codes,
        latest_only=latest_only
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
        
    return result 