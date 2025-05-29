import asyncio
import argparse
from datetime import datetime
import logging
import os
import re
import shutil
import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession
from stockeasy.services.financial.stock_info_service import StockInfoService
from stockeasy.services.financial.data_service_pdf import FinancialDataServicePDF
from common.core.config import settings
from common.core.database import AsyncSessionLocal, get_db_async, get_db_session
from stockeasy.services.financial.make_financial_db import MakeFinancialDataDB
from common.services.storage import GoogleCloudStorageService
import sys
import json
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='사업보고서에서 기수 및 사업년도 정보를 추출합니다.')
    parser.add_argument('--stock_code', type=str, help='종목 코드 (지정하지 않으면 모든 종목 처리)')
    parser.add_argument('--output', type=str, default='business_report_info.json', help='결과를 저장할 JSON 파일 경로')
    parser.add_argument('--max_reports', type=int, default=0, help='각 종목당 처리할 최대 보고서 수 (0=제한 없음)')
    parser.add_argument('--annual_only', action='store_true', help='연간 보고서만 처리')
    args = parser.parse_args()
    
    logger.info(f"사업보고서 기수 및 사업년도 정보 추출 시작")
    logger.info(f"설정: 종목코드={args.stock_code or '전체'}, 연간보고서만={args.annual_only}")
    
    # DB 세션 생성
    async with AsyncSessionLocal() as db_session:
        # 서비스 인스턴스 생성
        stock_service = StockInfoService()
        financial_service = FinancialDataServicePDF(db_session)
        
        # 처리할 종목 코드 목록 가져오기
        if args.stock_code:
            stock_codes = [args.stock_code]
        else:
            # 모든 종목 코드 가져오기
            stock_info_list = await stock_service.get_stock_info_list()
            stock_codes = [item.stock_code for item in stock_info_list]
            logger.info(f"총 {len(stock_codes)}개 종목을 처리합니다.")
        
        results = {}
        total_processed = 0
        
        # 각 종목별로 처리
        for stock_code in stock_codes:
            try:
                logger.info(f"종목 {stock_code} 처리 중...")
                
                # 해당 종목의 파일 목록 가져오기
                file_list = await financial_service._get_file_list(stock_code)
                # 마지막 파일 1개만 선택
                if file_list:
                    file_list = [file_list[-1]]
                    logger.info(f"마지막 파일 1개만 처리합니다: {os.path.basename(file_list[0].get('file_path', ''))}")
                
                # 필요한 경우 연간 보고서만 필터링
                if args.annual_only:
                    file_list = [file for file in file_list if file.get("type") == "annual"]
                
                logger.info(f"종목 {stock_code}의 보고서 {len(file_list)}개 찾았습니다.")
                
                # 최대 처리 수 제한 적용
                if args.max_reports > 0 and len(file_list) > args.max_reports:
                    file_list = file_list[:args.max_reports]
                    logger.info(f"최대 {args.max_reports}개만 처리합니다.")
                
                # 각 파일별로 정보 추출
                stock_results = []
                for file_info in file_list:
                    file_path = file_info.get("file_path")
                    local_path = await financial_service._ensure_local_file(file_path)
                    
                    if not local_path:
                        logger.warning(f"파일을 로컬에 다운로드할 수 없습니다: {file_path}")
                        continue
                    
                    # 기수 및 사업년도 정보 추출
                    report_info = await financial_service.extract_business_report_info(local_path)
                    
                    # 파일 정보 추가
                    report_info["file_name"] = os.path.basename(file_path)
                    report_info["report_date"] = file_info.get("date")
                    report_info["report_year"] = file_info.get("year")
                    report_info["report_type"] = file_info.get("type")
                    
                    stock_results.append(report_info)
                    logger.info(f"보고서 처리 완료: {os.path.basename(file_path)}")
                    total_processed += 1
                
                # 종목별 결과 저장
                if stock_results:
                    results[stock_code] = stock_results
                
            except Exception as e:
                logger.exception(f"종목 {stock_code} 처리 중 오류 발생: {str(e)}")
        
        # 결과를 JSON 파일로 저장
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"처리 완료: 총 {total_processed}개 보고서, 결과 저장 경로: {output_path.absolute()}")


if __name__ == "__main__":
    # Windows 환경에서 네이티브 ProactorEventLoop 사용을 위한 설정
    if sys.platform.startswith('win'):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main()) 