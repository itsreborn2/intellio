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
from common.core.database import get_db_async, get_db_session
from stockeasy.services.financial.make_financial_db import MakeFinancialDataDB
from common.services.storage import GoogleCloudStorageService
import sys

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


        ymd = f"{target_year}{target_month:02d}{target_day:02d}"
        file_name_new = f"{ymd}_{company_name}_{stock_code}_{sector}_{report_type}_DART.pdf"
        gcs_path_source = f"Stockeasy/classified/정기보고서/{stock_code}/{file_name}"
        gcs_path_destination = f"Stockeasy/classified/정기보고서/{stock_code}/{file_name_new}"
        
        await storage_service.move_file(gcs_path_source, gcs_path_destination)
        
        file_path_old = os.path.join(company_dir, file_name)
        file_path_new = os.path.join(company_dir, file_name_new)
        os.rename(file_path_old, file_path_new)

        print(f"파일명: {file_name}, 일자: {target_year}-{target_month:02d}-{target_day:02d}, GCS 수정")
        print(f"{file_name} -> {file_name_new}\n")

async def process_reports(db: AsyncSession, company_code: str, reports_dir: str, test_file: str = None, skip_annual_first: bool = True) -> bool:
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
        logger.info(f"회사 로컬 디렉토리가 없습니다: {company_dir}. GCS에서 다운로드를 시도합니다.")
        # 디렉토리가 없으면 생성
        os.makedirs(company_dir, exist_ok=True)
        # FinancialDataServicePDF를 사용하여 다운로드
        try:
            f = FinancialDataServicePDF(db) # db 세션 전달
            await f.get_financial_data(company_code, {"start_date": datetime(2020, 1, 1), "end_date": datetime(2025, 4, 1)})
        except Exception as e:
            logger.error(f"초기 다운로드 중 오류 발생 ({company_code}): {e}")
            # 오류 발생 시 디렉토리가 비어있을 수 있으므로 함수 종료 또는 다른 처리 필요
            return False


    # GCS 서비스 초기화
    storage_service = GoogleCloudStorageService(
        project_id=settings.GOOGLE_CLOUD_PROJECT,
        bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
        credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
    )
    gcs_prefix = f"Stockeasy/classified/정기보고서/{company_code}/"

    # GCS 파일 목록 조회 (파일만 필터링)

    # 이 함수가 GCS에서 파일 목록을 가져옵니다
    gcs_files = await storage_service.list_files_in_folder(gcs_prefix)
    # 디렉토리 자체나 빈 항목 제거
    gcs_files = [f for f in gcs_files if f != gcs_prefix and f.endswith(".pdf")]
    logger.info(f"GCS 파일 개수 ({company_code}): {len(gcs_files)}")


    # 로컬 보고서 파일 목록 조회
    local_report_files = [f for f in os.listdir(company_dir) if f.endswith(".pdf")]
    logger.info(f"로컬 파일 개수 ({company_code}): {len(local_report_files)}")

    # test_file이 없을때만, GCS 파일 개수가 로컬 파일 개수보다 많으면 다운로드 시도
    # 특정 파일을 지정한게 아니라, 종목을 지정한 케이스
    if len(gcs_files) > len(local_report_files):
        logger.info(f"GCS 파일({len(gcs_files)})이 로컬 파일({len(local_report_files)})보다 많아 다운로드를 시작합니다 ({company_code}).")
        try:
            # PDF 파일 다운로드 시 오류 처리 개선
            f = FinancialDataServicePDF(db) # db 세션 전달

            # 파일 다운로드 시도
            await f.get_financial_data(company_code, {"start_date": datetime(2020, 1, 1), "end_date": datetime(2025, 4, 1)})
            
            # 다운로드 후 로컬 파일 목록 다시 조회
            if os.path.exists(company_dir):
                local_report_files = [f for f in os.listdir(company_dir) if f.endswith(".pdf")]
                logger.info(f"다운로드 후 로컬 파일 개수 ({company_code}): {len(local_report_files)}")
            else:
                logger.warning(f"다운로드 후에도 로컬 디렉토리가 없습니다: {company_dir}")
                local_report_files = []
        except Exception as e:
            logger.error(f"다운로드 중 오류 발생 ({company_code}): {str(e)}")
            # 다운로드 실패 시에도 기존 로컬 파일로 계속 진행할지 결정 필요
            # 여기서는 일단 진행하도록 둡니다.

    # 서비스 초기화
    service = MakeFinancialDataDB(db)

    # 최종 처리할 보고서 파일 목록 (변수명 변경: report_files -> local_report_files)
    report_files = local_report_files # 최종적으로 사용할 변수명 유지

    if not report_files:
        logger.warning(f"처리할 보고서 파일이 없습니다: {company_dir}")
        return False

    # await temp_gcs(report_files, company_dir)
    # return

    # 첫 보고서가 annual인지 확인
    first_annual_skipped = True
    first_report_skipped = False

    test_mode = True
    if test_file is None or len(test_file) == 0:
        test_mode = False
    logger.info(f"test_mode: {test_mode}, test_file: {test_file}")

    # 파일을 날짜순으로 정렬 (오름차순 정렬. 옛날꺼부터 진행)
    report_files.sort(reverse=False)

    logger.info(f"처리할 보고서 파일: {len(report_files)}개")

    #for file_name in report_files[:5]:
    for i,file_name in enumerate(report_files):
        if first_report_skipped and not test_mode:
            first_report_skipped = False
            continue

        # 파일명 파싱: 일자_종목명_종목코드_섹터_보고서유형_DART.pdf
        # 예: 20200330_SK하이닉스_000660_전기·전자_annual_DART.pdf
        print(f"test_mode: {test_mode}, test_file: {test_file}, file_name: {file_name}")
        if test_mode and not test_file in file_name:
            continue
        parts = file_name.split("_")
        if len(parts) < 6:  # 최소 6개 부분이 있어야 함
            logger.warning(f"파일명 형식이 맞지 않습니다: {file_name}")
            continue

        try:
            # 일자 추출 (첫 번째 부분)
            date_str = parts[0]
            year = int(date_str[:4])
            
            # 날짜 형식 처리 개선: YYYYMM00 형식 처리
            if date_str[6:8] == '00':
                month = int(date_str[4:6])
                day = 1  # 일자가 00인 경우 1일로 처리
                logger.info(f"날짜 형식 보정: {date_str} -> {year}-{month:02d}-{day:02d}")
            else:
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
                #year = year - 1
                
                # # 첫 번째 annual 보고서를 건너뛰는 로직.테스트 모드가 아닐때만 적용.
                # 테스트 모드에선는 적용되지 않음.
                if not test_mode and skip_annual_first and not first_annual_skipped and i == 0: # 첫번째 보고서가 연간 보고서인 경우에 건너뜀.
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
            
            # PDF 파일이 유효한지 확인
            try:
                with open(file_path, 'rb') as f:
                    if f.read(5) != b'%PDF-':
                        logger.warning(f"유효하지 않은 PDF 파일입니다: {file_name}")
                        continue
            except Exception as pdf_err:
                logger.error(f"PDF 파일 검증 오류: {file_name}, 오류: {str(pdf_err)}")
                continue
                
            # 요약재무정보 처리
            try:
                result = await service.process_financial_summary(
                    company_code=company_code,
                    report_file_path=file_path,
                    report_type=report_type,
                    report_year=year,
                    report_quarter=quarter
                )
                
                if result["success"]:
                    logger.info(f"처리 완료: {file_name}, 항목 수: {result['details'].get('items_count', 0)}")
                    # 로컬에서 파일 처리 후 삭제.
                    if test_file:
                        tmp_file_path = f'stockeasy/local_cache/tmp/{file_name}'
                        os.remove(tmp_file_path)
                        print(f"완료 후 파일 삭제 : {tmp_file_path}")
                else:
                    logger.error(f"처리 실패: {file_name}, 오류: {result['message']}")
            except Exception as process_err:
                logger.error(f"재무정보 처리 중 오류 발생: {file_name}, 오류: {str(process_err)}")
                # 오류가 발생해도 다음 파일 처리 계속
                continue
                
        except Exception as e:
            logger.error(f"파일 처리 중 오류 발생: {file_name}, 오류: {str(e)}")
            continue
    return True

async def process_one_company(company_code: str, reports_dir: str, test_file: str = None, skip_annual_first: bool = True):
    """
    개별 회사 코드를 처리하는 함수
    
    Args:
        company_code: 회사 코드
        reports_dir: 보고서 파일 디렉토리
        test_file: 테스트할 파일명
        skip_annual_first: 첫 보고서가 annual인 경우 건너뛸지 여부
    """
    db = None
    try:
        if test_file:
            company_code = test_file.split("_")[2]
            print(f"테스트 파일 있음. 파일만 처리: {test_file}")
        db = await get_db_session()
        logger.info(f"회사 코드 처리 시작: {company_code}")
        result = await process_reports(db=db, company_code=company_code, reports_dir=reports_dir, 
                              test_file=test_file, skip_annual_first=skip_annual_first)
        if result:
            logger.info(f"회사 코드 처리 완료: {company_code}")
        else:
            logger.error(f"회사 코드 처리 실패: {company_code}")
        return result
    except Exception as e:
        logger.error(f"회사 코드 처리 중 오류 발생: {company_code}, 오류: {str(e)}")
    finally:
        if db:
            try:
                # 세션 정리 전 pending 트랜잭션 롤백 시도
                await db.rollback()
                logger.debug(f"DB 세션 롤백 완료: {company_code}")
            except Exception as e:
                logger.error(f"DB 세션 롤백 중 오류 발생: {company_code}, 오류: {str(e)}")
            
            try:
                # 세션 닫기
                await db.close()
                logger.debug(f"DB 세션 닫기 완료: {company_code}")
            except Exception as e:
                logger.error(f"DB 세션 닫기 중 오류 발생: {company_code}, 오류: {str(e)}")


async def process_companies(code_list: list, reports_dir: str, test_file: str = None, 
                           skip_annual_first: bool = True, batch_size: int = 3):
    """
    회사 코드 목록을 배치 단위로 병렬 처리하는 함수
    
    Args:
        code_list: 회사 코드 목록
        reports_dir: 보고서 파일 디렉토리
        test_file: 테스트할 파일명
        skip_annual_first: 첫 보고서가 annual인 경우 건너뛸지 여부
        batch_size: 한 번에 처리할 회사 수 (기본값: 3, DB 연결 풀 부하 감소)
    """
    total_companies = len(code_list)
    logger.info(f"총 처리할 회사 수: {total_companies}개, 배치 크기: {batch_size}개")
    
    # 코드 목록을 batch_size 크기의 청크로 분할
    for i in range(0, total_companies, batch_size):
        batch = code_list[i:i+batch_size]
        logger.info(f"배치 처리 시작: {i//batch_size + 1}/{(total_companies + batch_size - 1)//batch_size}, " 
                    f"회사 수: {len(batch)}개 ({i+1}~{min(i+batch_size, total_companies)})")
        
        # 현재 배치의 작업들을 병렬로 실행
        tasks = [process_one_company(code, reports_dir, test_file, skip_annual_first) for code in batch]
        await asyncio.gather(*tasks)
        
        # 각 배치 사이에 대기 시간 추가하여 DB 연결 정리 시간 확보
        if i + batch_size < total_companies:
            wait_time = 3  # 1초에서 3초로 증가
            logger.info(f"다음 배치 처리 전 {wait_time}초 대기 중...")
            await asyncio.sleep(wait_time)
        
        logger.info(f"배치 처리 완료: {i//batch_size + 1}/{(total_companies + batch_size - 1)//batch_size}")


async def process_companies_each_files(file_list: list, reports_dir: str, batch_size: int = 3):
    """
    회사 코드 목록을 배치 단위로 병렬 처리하는 함수
    
    Args:
        code_list: 회사 코드 목록
        reports_dir: 보고서 파일 디렉토리
        test_file: 테스트할 파일명
        skip_annual_first: 첫 보고서가 annual인 경우 건너뛸지 여부
        batch_size: 한 번에 처리할 회사 수 (기본값: 3, DB 연결 풀 부하 감소)
    """
    total_files = len(file_list)
    logger.info(f"총 처리할 회사 수: {total_files}개, 배치 크기: {batch_size}개")
    
    # 코드 목록을 batch_size 크기의 청크로 분할
    for i in range(0, total_files, batch_size):
        batch = file_list[i:i+batch_size]
        logger.info(f"배치 처리 시작: {i//batch_size + 1}/{(total_files + batch_size - 1)//batch_size}, " 
                    f"회사 수: {len(batch)}개 ({i+1}~{min(i+batch_size, total_files)})")
        
        # 현재 배치의 작업들을 병렬로 실행
        tasks = [process_one_company(None, reports_dir, test_file, False) for test_file in batch]
        await asyncio.gather(*tasks)
        
        # 각 배치 사이에 대기 시간 추가하여 DB 연결 정리 시간 확보
        if i + batch_size < total_files:
            wait_time = 3  # 1초에서 3초로 증가
            logger.info(f"다음 배치 처리 전 {wait_time}초 대기 중...")
            await asyncio.sleep(wait_time)
        
        logger.info(f"배치 처리 완료: {i//batch_size + 1}/{(total_files + batch_size - 1)//batch_size}")

async def extract_error_files():
    with open("stockeasy/local_cache/financial_reports_error_log_extrace.txt", "w", encoding="utf-8") as ef:
        with open("stockeasy/local_cache/financial_reports_error_log.txt", "r", encoding="utf-8") as f:
            prev_line = ""
            for line in f:
                if ", 오류=PostgreSQL server at \"pgbouncer:6432" in line:
                    ef.write(line)
    
    await remove_duplicate_lines("stockeasy/local_cache/financial_reports_error_log_extrace.txt")

async def remove_duplicate_lines(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(file_path, "w", encoding="utf-8") as f:
        prev_line_tail = ""
        for line in lines:
            # 현재 라인에서 줄바꿈과 앞뒤 공백 제거
            clean_line = line.strip()
            # 빈 라인이면 그냥 기록
            if not clean_line:
                f.write(line)
                continue
                
            # 현재 라인의 마지막 50자만 추출 (공백 등 정규화 후)
            clean_line = ' '.join(clean_line.split())  # 연속된 공백을 하나로 통일
            current_line_tail = clean_line[-50:] if len(clean_line) >= 50 else clean_line
            
            # 이전 라인의 마지막 부분과 다르면 기록
            if current_line_tail != prev_line_tail:
                #print(f"{prev_line_tail} <-> {current_line_tail}")
                f.write(line)
                prev_line_tail = current_line_tail
async def get_gcs_new_files(storage_service):
    # GCS 서비스 초기화
    
    gcs_path = 'Stockeasy/collected_auto/정기보고서(첨부정정원본보고서)/'
    gcs_files = await storage_service.list_files_in_folder(gcs_path)
    #new_files = [os.path.basename(f) for f in gcs_files if f.endswith(".pdf")]
    return gcs_files
async def make_code_list():
    code_list = []
    file_list = []
    # backend\stockeasy\local_cache\tmp\20210300_iM금융지주_139130_기타금융_Q1_DART.pdf
    for f in os.listdir('stockeasy/local_cache/tmp'):
        if f.endswith(".pdf"):
            code = f.split("_")[2]
            date = f.split("_")[0]
            year = int(date[:4])
            if year < 2025:  # 2025년 이후 보고서만
                continue
            #code_list.append(code)
            file_list.append(  os.path.basename(f) )
    return file_list
async def move_file_to_classified(file_list: list = None):
    """
    원본 위치(Stockeasy/collected_auto/정기보고서/)에서 사업보고서 파일을 읽어서
    파일명의 날짜 부분을 확인하여 일자가 00인 경우 01로 수정하고
    새로운 위치(Stockeasy/classified/정기보고서/{종목코드}/)로 이동합니다.
    
    Args:
        file_list: 처리할 파일 목록 (없으면 모든 파일 처리)
    """
    storage_service = GoogleCloudStorageService(
        project_id=settings.GOOGLE_CLOUD_PROJECT,
        bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
        credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
    )
    gcs_path = 'Stockeasy/collected_auto/정기보고서/'
    target_gcs_base = 'Stockeasy/classified/정기보고서/'
    
    # 원본 디렉토리의 모든 파일 목록 가져오기
    gcs_files = await storage_service.list_files_in_folder(gcs_path)
    processed_files = []
    
    logger.info(f"원본 위치에서 {len(gcs_files)}개 파일 발견")
    
    for blob_path in gcs_files:
        try:
            base_file_name = os.path.basename(blob_path)
            
            # 파일 이름 형식 검증
            parts = base_file_name.split('_')
            if len(parts) < 6:
                logger.warning(f"파일명 형식이 맞지 않습니다: {base_file_name}")
                continue
            
            # 특정 파일 목록이 제공된 경우 해당 파일만 처리
            if file_list and base_file_name not in file_list:
                continue
            
            # 종목코드 및 날짜 추출
            date_str = parts[0]
            company_code = parts[2]
            
            # 새 파일명 계산 (일자가 00인 경우 01로 수정)
            new_file_name = base_file_name
            if len(date_str) == 8 and date_str[6:8] == '00':
                new_date_str = date_str[:6] + '01'
                new_file_name = base_file_name.replace(date_str, new_date_str, 1)
                logger.info(f"파일명 날짜 수정: {base_file_name} -> {new_file_name}")
            
            # 이동할 타겟 경로 생성
            target_gcs_path = f"{target_gcs_base}{company_code}/{new_file_name}"
            
            # 파일 이동
            await storage_service.move_file(blob_path, target_gcs_path)
            logger.info(f"파일 이동 완료: {base_file_name} -> {target_gcs_path}")
            
            processed_files.append(new_file_name)
            
        except Exception as e:
            logger.error(f"파일 처리 중 오류 발생: {blob_path}, 오류: {str(e)}")
    
    logger.info(f"총 {len(processed_files)}개 파일이 새 위치로 이동되었습니다.")
    return processed_files
async def make_new_file_list_from_gcs_정기보고서():
    """
    GCS intellio-stockeasy-storage/Stockeasy/collected_auto/정기보고서 에 남아있는 파일 리스트를 가져온다.
    """
    storage_service = GoogleCloudStorageService(
        project_id=settings.GOOGLE_CLOUD_PROJECT,
        bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
        credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
)
    gcs_path = 'Stockeasy/collected_auto/정기보고서/'
    target_gcs_base = 'Stockeasy/classified/정기보고서/'
    gcs_files = await storage_service.list_files_in_folder(gcs_path)
    file_list = []

    for blob in gcs_files:
        base_file_name = os.path.basename(blob)
        tmp_path = 'stockeasy/local_cache/tmp'
        os.makedirs(tmp_path, exist_ok=True)
        if not os.path.exists(os.path.join(tmp_path, base_file_name)):
            content = await storage_service.download_file(blob)
            saved_file_path = os.path.join(tmp_path, base_file_name)
            with open(saved_file_path, 'wb') as f:
                f.write(content)
            file_list.append(saved_file_path)

            


    return file_list
async def change_file_name_wrong_date():
    """
    파일 이름의 날짜 부분에서 일자가 00으로 되어 있는 파일을 찾아 01로 변경합니다.
    예: 20231200_회사명_코드_... -> 20231201_회사명_코드_...
    """
    tmp_path = 'stockeasy/local_cache/tmp'
    os.makedirs(tmp_path, exist_ok=True)
    
    # 디렉토리의 모든 PDF 파일 가져오기
    files = [f for f in os.listdir(tmp_path) if f.endswith('.pdf')]
    renamed_count = 0
    
    for file_name in files:
        parts = file_name.split('_')
        if len(parts) < 6:  # 파일명 형식 확인
            logger.warning(f"파일명 형식이 맞지 않습니다: {file_name}")
            continue
        
        # 날짜 부분 확인 (첫 번째 부분)
        date_str = parts[0]
        if len(date_str) == 8 and date_str[6:8] == '00':
            # 일자가 00인 경우 01로 변경
            new_date_str = date_str[:6] + '01'
            new_file_name = file_name.replace(date_str, new_date_str, 1)
            
            # 파일 이름 변경
            old_path = os.path.join(tmp_path, file_name)
            new_path = os.path.join(tmp_path, new_file_name)
            
            try:
                os.rename(old_path, new_path)
                renamed_count += 1
                logger.info(f"파일명 변경: {file_name} -> {new_file_name}")
            except Exception as e:
                logger.error(f"파일명 변경 중 오류 발생: {file_name}, 오류: {str(e)}")
    
    logger.info(f"총 {renamed_count}개 파일의 이름이 변경되었습니다.")
    return renamed_count
async def main():
    """메인 함수"""
    
    parser = argparse.ArgumentParser(description="요약재무정보 추출")
    parser.add_argument("--company", required=True, help="회사 코드 (예: 005930)")
    parser.add_argument("--dir", default="stockeasy/local_cache/financial_reports", help="보고서 파일 디렉토리")
    parser.add_argument("--process-all", action="store_true", help="모든 보고서 처리 (첫 annual 건너뛰기 없음)")
    parser.add_argument("--batch-size", type=int, default=3, help="한 번에 병렬로 처리할 회사 수 (기본값: 3)")
    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 20230321_한국콜마_161890_화학_annual_DART
    tmp_file_list = await make_code_list()
    #tmp_file_list = await make_new_file_list_from_gcs_정기보고서()
    print(f"tmp_file_list: {len(tmp_file_list)}")
    #tmp_file_list = tmp_file_list[:1]
    test_file = ""
    if test_file:
        tmp_code = test_file.split("_")[2]
        args.company = tmp_code

    stock_info_service = StockInfoService()
    await asyncio.sleep(0.5)  # 1초만 대기 후 진행
    all_code_list = await stock_info_service.get_all_stock_codes()
    #all_code_list = ["900100","900140","900070","008700","950130","950210","950220","241560","950140","950160","950190"]
    end_index = len(all_code_list)
    end_index = len(tmp_file_list)
    start_index = 0#1037
    window_size = 100

        
    try:
        print(f"args.company: {args.company}")
        if args.company and args.company == "all":
        # 여기 for문 작성
            tmp_list = []
            for current_index in range(start_index, end_index, window_size):
                end = min(current_index + window_size, end_index)
                tmp_list = tmp_file_list[current_index:end]
                #code_list = all_code_list[current_index:end]
                
                #print(f"현재 처리 범위: {current_index} ~ {end-1}, 종목 수: {len(code_list)}")
                print(f"현재 처리 범위: {current_index} ~ {end-1}, 종목 수: {len(tmp_list)}")
                
                # 병렬 처리 실행
                # await process_companies(
                #     code_list=code_list,
                #     reports_dir=args.dir,
                #     test_file=test_file,
                #     skip_annual_first=not args.process_all,
                #     batch_size=args.batch_size
                # )
                
                await process_companies_each_files(
                    file_list=tmp_list,
                    reports_dir=args.dir,
                    batch_size=args.batch_size
                )

            print(f"처리된 종목코드 : {tmp_list}")

        else:
            #단일 종목, 개별테스트
            print(f"테스트 처리할 회사 코드: {args.company}")
            code_list = [args.company]
            #code_list = ["323410","175330","138930","055550","105560","041920"]
            await process_companies(
                code_list=code_list,
                reports_dir=args.dir,
                test_file=test_file,
                skip_annual_first=not args.process_all,
                batch_size=args.batch_size
            )
                
    except Exception as e:
        logger.error(f"작업 중 오류 발생: {e}")
        raise


if __name__ == "__main__":
    # Windows 환경에서 네이티브 ProactorEventLoop 사용을 위한 설정
    if sys.platform.startswith('win'):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main()) 