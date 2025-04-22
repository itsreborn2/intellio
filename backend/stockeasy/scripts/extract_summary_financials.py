import asyncio
import argparse
from datetime import datetime
import logging
import os
import re
import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession
from stockeasy.services.financial.data_service import FinancialDataServicePDF
from common.core.config import settings
from common.core.database import get_db_async, get_db_session
from stockeasy.services.financial.data_service_db import FinancialDataServiceDB
from common.services.storage import GoogleCloudStorageService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정

async def check_1page_정정신고(report_file_path: str) -> str:
    """
    PDF 파일의 1페이지를 읽어서 정정신고 여부를 확인하고 파일명을 변경합니다.
    
    Args:
        report_file_path: 보고서 파일 경로
        
    Returns:
        수정된 파일 경로 또는 원래 파일 경로
    """
    #logger.info(f"정정신고 확인 중: {report_file_path}")
    
    try:
        # 파일 경로 확인
        if not os.path.exists(report_file_path):
            logger.error(f"파일이 존재하지 않습니다: {report_file_path}")
            return report_file_path
        
        # PDFplumber로 PDF 파일 1페이지(목차) 읽기
        with pdfplumber.open(report_file_path) as pdf:
            if len(pdf.pages) == 0:
                logger.warning(f"PDF 파일에 페이지가 없습니다: {report_file_path}")
                return report_file_path
            
            # 첫 페이지 텍스트 추출
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            if not text:
                logger.warning(f"PDF 첫 페이지 텍스트를 추출할 수 없습니다: {report_file_path}")
                return report_file_path
            
            # 정정신고 키워드 확인
            if "정정신고" not in text and "정 정 신 고" not in text:
                #logger.info(f"정정신고가 아닙니다: {report_file_path}")
                return report_file_path
            
            logger.info(f"정정신고 발견: {report_file_path}")
            
            # 정정신고 페이지 확인
            correction_page = None
            skipFirstWord = True
            for i, page in enumerate(pdf.pages[:min(5, len(pdf.pages))]):  # 처음 5개 페이지만 확인
                page_text = page.extract_text()
                if "정정신고" in page_text or "정 정 신 고" in page_text:
                    if skipFirstWord:
                        skipFirstWord = False
                        continue
                    correction_page = i
                    break
            #logger.info(f"정정신고 페이지: {correction_page}")
            if correction_page is None:
                logger.warning(f"정정신고 페이지를 찾을 수 없습니다: {report_file_path}")
                return report_file_path
            
            # 최초제출일 추출
            correction_text = pdf.pages[correction_page].extract_text()
            
            # 정정대상 공시서류 관련 문구 찾기
            matches = []
            
            # 패턴 1: 일반적인 '최초제출일' 패턴
            pattern1 = r'최초제출일\s*:?\s*(\d{4})[\s\.\-년]?(\d{1,2})[\s\.\-월]?(\d{1,2})[\s일]?'
            
            # 패턴 2: '정정대상 공시서류의 최초제출일' 패턴
            pattern2 = r'정정대상\s*공시서류의\s*최초제출일\s*:?\s*(\d{4})[\s\.\-년]?\s*(\d{1,2})[\s\.\-월]?\s*(\d{1,2})[\s일]?'
            
            # 패턴 3: 번호로 시작하는 정정사항 패턴
            pattern3 = r'\d+\.\s*정정대상\s*공시서류의\s*최초제출일\s*:?\s*(\d{4})[\s\.\-년]?\s*(\d{1,2})[\s\.\-월]?\s*(\d{1,2})[\s일]?'
            
            # 먼저 더 구체적인 패턴 3 시도
            original_date_match = re.search(pattern3, correction_text)
            if not original_date_match:
                # 패턴 2 시도
                original_date_match = re.search(pattern2, correction_text)
            if not original_date_match:
                # 패턴 1 시도
                original_date_match = re.search(pattern1, correction_text)
            
            logger.info(f"최초제출일 포맷 확인: {original_date_match}")
            
            if not original_date_match:
                logger.warning(f"최초제출일을 찾을 수 없습니다: {report_file_path}")
                print(correction_text)
                # 디버깅을 위해 패턴별로 직접 검색해보기
                logger.info(f"패턴1 결과: {re.search(pattern1, correction_text)}")
                logger.info(f"패턴2 결과: {re.search(pattern2, correction_text)}")
                logger.info(f"패턴3 결과: {re.search(pattern3, correction_text)}")
                return report_file_path
            
            # 원본 날짜 추출
            year = original_date_match.group(1)
            month = original_date_match.group(2).zfill(2)
            day = original_date_match.group(3).zfill(2)
            original_date = f"{year}{month}{day}"
            
            # 파일명 변경
            file_dir = os.path.dirname(report_file_path)
            file_name = os.path.basename(report_file_path)
            
            # 파일명 파싱: 일자_종목명_종목코드_섹터_보고서유형_DART.pdf
            parts = file_name.split("_")
            if len(parts) < 6:
                logger.warning(f"파일명 형식이 맞지 않습니다: {file_name}")
                return report_file_path
            
            current_date = parts[0]
            if current_date == original_date:
                logger.info(f"정정신고 파일의 날짜가 이미 최초제출일과 동일합니다: {file_name}")
                return report_file_path
            
            # 새 파일명 생성
            parts[0] = original_date
            new_file_name = "_".join(parts)
            new_file_path = os.path.join(file_dir, new_file_name)
            
            # 파일 이동
            logger.info(f"파일명 변경: {file_name} -> {new_file_name}")
            os.rename(report_file_path, new_file_path)
            
            # GCS 파일 경로 변경
            try:
                # GCS 경로 구성
                stock_code = parts[2]
                gcs_dir = f"Stockeasy/classified/정기보고서/{stock_code}"
                old_gcs_path = f"{gcs_dir}/{file_name}"
                new_gcs_path = f"{gcs_dir}/{new_file_name}"
                
                # GCS 서비스 초기화
                storage_service = GoogleCloudStorageService(
                    project_id=settings.GOOGLE_CLOUD_PROJECT,
                    bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
                    credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
                )
                await storage_service.move_file(old_gcs_path, new_gcs_path)
                
            except Exception as e:
                logger.error(f"GCS 파일 경로 변경 중 오류 발생: {str(e)}")
            
            return new_file_path
            
    except Exception as e:
        logger.error(f"정정신고 확인 중 오류 발생: {str(e)}")
        return report_file_path

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
        f = FinancialDataServicePDF(db)
        await f.get_financial_data(company_code, {"start_date": datetime(2020, 1, 1), "end_date": datetime(2025, 4, 1)})

    
    # 서비스 초기화
    service = FinancialDataServiceDB(db)
    
    # 보고서 파일 목록 조회
    report_files = [f for f in os.listdir(company_dir) if f.endswith(".pdf")]
    
    if not report_files:
        logger.warning(f"보고서 파일이 없습니다: {company_dir}")
        f = FinancialDataServicePDF(db)
        await f.get_financial_data(company_code, {"start_date": datetime(2020, 1, 1), "end_date": datetime(2025, 4, 1)})

    report_files = [f for f in os.listdir(company_dir) if f.endswith(".pdf")]
    
    if not report_files:
        logger.warning(f"보고서 파일이 없습니다: {company_dir}")
        return
    
    test_mode = False
    if not test_mode:
        for report in report_files:
            file_path = os.path.join(company_dir, report)
            modified_path = await check_1page_정정신고(file_path)

        # 변경된 파일 목록 다시 가져오기
        report_files = [f for f in os.listdir(company_dir) if f.endswith(".pdf")]
    
    # 파일을 날짜순으로 정렬 (오름차순 정렬. 옛날꺼부터 진행)
    report_files.sort(reverse=False)
    
    logger.info(f"처리할 보고서 파일: {len(report_files)}개")
    
    # 첫 보고서가 annual인지 확인
    first_annual_skipped = True
    first_report_skipped = False
    
    #for file_name in report_files[:5]:
    for file_name in report_files:
        if first_report_skipped and not test_mode:
            first_report_skipped = False
            continue

        # 파일명 파싱: 일자_종목명_종목코드_섹터_보고서유형_DART.pdf
        # 예: 20200330_SK하이닉스_000660_전기·전자_annual_DART.pdf

        # if not "20230515_SK하이닉스_000660_전기·전자_Q1_DART" in file_name:
        #     continue
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
            
            if "annual" == report_type_str:
                report_type = "annual"
                quarter = 4
                # 연간 보고서의 경우 실제 데이터는 이전 연도의 것
                year = year - 1
                
                # # 첫 번째 annual 보고서를 건너뛰는 로직
                # if skip_annual_first and not first_annual_skipped:
                #     logger.info(f"첫 annual 보고서 건너뛰기: {file_name}")
                #     first_annual_skipped = True
                #     continue
                    
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