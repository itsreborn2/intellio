import asyncio
import argparse
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession
from common.core.config import settings
from common.core.database import get_db_async, get_db_session
from stockeasy.services.financial.data_service import FinancialDataService

logger = logging.getLogger(__name__)


async def process_reports(db: AsyncSession, company_code: str, reports_dir: str, skip_annual_first: bool = True):
    """
    특정 회사의 보고서 파일을 읽어 요약재무정보 추출
    
    Args:
        db: 데이터베이스 세션
        company_code: 회사 코드
        reports_dir: 보고서 파일 디렉토리
        skip_annual_first: 첫 보고서가 annual인 경우 건너뛸지 여부
    """
    # 파일 경로 확인
    company_dir = os.path.join(reports_dir, "정기보고서", company_code)
    if not os.path.exists(company_dir):
        logger.error(f"회사 디렉토리가 없습니다: {company_dir}")
        return
    
    # 서비스 초기화
    service = FinancialDataService(db)
    
    # 보고서 파일 목록 조회
    report_files = [f for f in os.listdir(company_dir) if f.endswith(".pdf")]
    
    if not report_files:
        logger.warning(f"보고서 파일이 없습니다: {company_dir}")
        return
    
    # 파일을 날짜순으로 정렬 (오름차순 정렬. 옛날꺼부터 진행)
    report_files.sort(reverse=False)
    
    logger.info(f"처리할 보고서 파일: {len(report_files)}개")
    
    # 첫 보고서가 annual인지 확인
    first_annual_skipped = False
    
    for file_name in report_files[:2]:
        # 파일명 파싱: 일자_종목명_종목코드_섹터_보고서유형_DART.pdf
        # 예: 20200330_SK하이닉스_000660_전기·전자_annual_DART.pdf
        parts = file_name.split("_")
        if len(parts) < 6:  # 최소 6개 부분이 있어야 함
            logger.warning(f"파일명 형식이 맞지 않습니다: {file_name}")
            continue
        
        try:
            # 일자 추출 (첫 번째 부분)
            date_str = parts[0]
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            
            # 종목 정보 추출
            company_name = parts[1]  # 종목명
            stock_code = parts[2]    # 종목코드
            sector = parts[3]        # 섹터
            
            # 보고서 유형 추출 (다섯 번째 부분)
            report_type_str = parts[4].lower()  # 소문자로 변환하여 비교 안정성 향상
            
            # 보고서 유형 및 분기 판별
            report_type = ""
            quarter = None
            
            if "annual" in report_type_str:
                report_type = "annual"
                # 연간 보고서의 경우 실제 데이터는 이전 연도의 것
                year = year - 1
                
                # 첫 번째 annual 보고서를 건너뛰는 로직
                if skip_annual_first and not first_annual_skipped:
                    logger.info(f"첫 annual 보고서 건너뛰기: {file_name}")
                    first_annual_skipped = True
                    continue
                    
            elif "semi" in report_type_str or "반기" in report_type_str:
                report_type = "semi"
                quarter = 2
            elif "q1" in report_type_str or "1분기" in report_type_str:
                report_type = "quarter"
                quarter = 1
            elif "q2" in report_type_str or "2분기" in report_type_str:
                report_type = "quarter" 
                quarter = 2
            elif "q3" in report_type_str or "3분기" in report_type_str:
                report_type = "quarter"
                quarter = 3
            elif "q4" in report_type_str or "4분기" in report_type_str:
                report_type = "quarter"
                quarter = 4
            else:
                logger.warning(f"알 수 없는 보고서 유형: {report_type_str}, 파일: {file_name}")
                continue
            
            # 파일 전체 경로
            file_path = os.path.join(company_dir, file_name)
            
            # 정보 출력
            logger.info(f"처리 중: {file_name}")
            logger.info(f"  날짜: {year}-{month:02d}-{day:02d}, 회사: {company_name}({company_code}), 유형: {report_type}, 분기: {quarter if quarter else '연간'}")
            
            # 요약재무정보 처리
            result = await service.process_financial_summary(
                company_code=company_code,
                report_file_path=file_path,
                report_type=report_type,
                report_year=year,
                report_quarter=quarter
            )
            
            if result["success"]:
                logger.info(f"처리 완료: {file_name}, 항목 수: {result['details'].get('items_count', 0)}")
            else:
                logger.error(f"처리 실패: {file_name}, 오류: {result['message']}")
                
        except Exception as e:
            logger.error(f"파일 처리 중 오류 발생: {file_name}, 오류: {str(e)}")
            continue


async def main():
    """메인 함수"""
    print(f"데이터베이스 설정 확인:")
    print(f"호스트: {settings.POSTGRES_HOST}")
    print(f"포트: {settings.POSTGRES_PORT}")
    print(f"DB: {settings.POSTGRES_DB}")
    print(f"유저: {settings.POSTGRES_USER}")
    
    parser = argparse.ArgumentParser(description="요약재무정보 추출")
    parser.add_argument("--company", required=True, help="회사 코드 (예: 005930)")
    parser.add_argument("--dir", default="data/reports", help="보고서 파일 디렉토리")
    parser.add_argument("--process-all", action="store_true", help="모든 보고서 처리 (첫 annual 건너뛰기 없음)")
    args = parser.parse_args()
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    try:
        db = None
        try:
            db = await get_db_session()
            await process_reports(db, args.company, args.dir, not args.process_all)
            
        finally:
            await db.close()
            
    except Exception as e:
        logger.error(f"작업 중 오류 발생: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 