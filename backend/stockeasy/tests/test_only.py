import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

# # 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력용 핸들러
    ],
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정
logging.getLogger("pdfminer").setLevel(logging.ERROR)


def extract_tables_from_page(pdf_path: str, page_number: int) -> List[List[List[str]]]:
    """
    PDF 파일의 특정 페이지에서 테이블을 추출하는 함수

    Args:
        pdf_path (str): PDF 파일 경로
        page_number (int): 추출할 페이지 번호 (1부터 시작)

    Returns:
        List[List[List[str]]]: 추출된 테이블들의 리스트
    """
    try:
        logger.info(f"PDF 파일 열기 시작: {pdf_path}")

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"총 페이지 수: {total_pages}")

            if page_number < 1 or page_number > total_pages:
                raise ValueError(f"페이지 번호가 범위를 벗어났습니다. (1-{total_pages})")

            # 페이지는 0부터 시작하므로 -1
            page = pdf.pages[page_number - 1]
            logger.info(f"페이지 {page_number} 테이블 추출 시작")

            tables = page.extract_tables()
            logger.info(f"페이지 {page_number}에서 {len(tables)}개의 테이블을 찾았습니다.")
            logger.info(tables)

            return tables

    except Exception as e:
        logger.error(f"테이블 추출 중 오류 발생: {str(e)}")
        raise


def extract_tables_with_settings(pdf_path: str, page_number: int, table_settings: Optional[Dict[str, Any]] = None) -> List[List[List[str]]]:
    """
    PDF 파일의 특정 페이지에서 설정을 적용하여 테이블을 추출하는 함수

    Args:
        pdf_path (str): PDF 파일 경로
        page_number (int): 추출할 페이지 번호 (1부터 시작)
        table_settings (Dict[str, Any], optional): 테이블 추출 설정

    Returns:
        List[List[List[str]]]: 추출된 테이블들의 리스트
    """
    try:
        # 기본 테이블 설정 (pdfplumber에서 지원하는 파라미터만 사용)
        default_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "edge_min_length": 3,
            "min_words_vertical": 3,
            "min_words_horizontal": 1,
            "text_tolerance": 3,
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,
        }

        if table_settings:
            default_settings.update(table_settings)

        logger.info(f"PDF 파일 열기 시작: {pdf_path}")
        logger.info(f"테이블 추출 설정: {default_settings}")

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"총 페이지 수: {total_pages}")

            if page_number < 1 or page_number > total_pages:
                raise ValueError(f"페이지 번호가 범위를 벗어났습니다. (1-{total_pages})")

            page = pdf.pages[page_number - 1]
            logger.info(f"페이지 {page_number} 테이블 추출 시작 (설정 적용)")

            tables = page.extract_tables(table_settings=default_settings)
            logger.info(f"페이지 {page_number}에서 {len(tables)}개의 테이블을 찾았습니다.")

            return tables

    except Exception as e:
        logger.error(f"테이블 추출 중 오류 발생: {str(e)}")
        raise


def extract_tables_from_multiple_pages(pdf_path: str, page_numbers: List[int]) -> Dict[int, List[List[List[str]]]]:
    """
    PDF 파일의 여러 페이지에서 테이블을 추출하는 함수

    Args:
        pdf_path (str): PDF 파일 경로
        page_numbers (List[int]): 추출할 페이지 번호들 (1부터 시작)

    Returns:
        Dict[int, List[List[List[str]]]]: 페이지별 추출된 테이블들의 딕셔너리
    """
    try:
        logger.info(f"PDF 파일 열기 시작: {pdf_path}")

        results = {}

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"총 페이지 수: {total_pages}")

            for page_num in page_numbers:
                if page_num < 1 or page_num > total_pages:
                    logger.warning(f"페이지 {page_num}는 범위를 벗어나서 건너뜁니다. (1-{total_pages})")
                    continue

                page = pdf.pages[page_num - 1]
                logger.info(f"페이지 {page_num} 테이블 추출 시작")

                tables = page.extract_tables()
                results[page_num] = tables
                logger.info(f"페이지 {page_num}에서 {len(tables)}개의 테이블을 찾았습니다.")

            logger.info(f"총 {len(results)}개 페이지에서 테이블 추출 완료")
            return results

    except Exception as e:
        logger.error(f"테이블 추출 중 오류 발생: {str(e)}")
        raise


def print_table_info(tables: List[List[List[str]]], page_number: int = None):
    """
    추출된 테이블 정보를 출력하는 헬퍼 함수

    Args:
        tables (List[List[List[str]]]): 추출된 테이블들
        page_number (int, optional): 페이지 번호
    """
    page_info = f"페이지 {page_number}" if page_number else "테이블"
    logger.info(f"{page_info} 테이블 정보:")

    for i, table in enumerate(tables):
        if table:
            rows = len(table)
            cols = len(table[0]) if table else 0
            logger.info(f"  테이블 {i + 1}: {rows}행 x {cols}열")

            # 첫 번째 행 출력 (헤더)
            if table and table[0]:
                header = " | ".join([cell or "" for cell in table[0]])
                logger.info(f"    헤더: {header}")
        else:
            logger.info(f"  테이블 {i + 1}: 빈 테이블")


# 테스트 함수 예시
def test_extract_tables():
    """
    테이블 추출 함수들을 테스트하는 함수
    """
    # PDF 파일 경로 (실제 파일 경로로 변경 필요)
    pdf_path = "test_sample.pdf"
    pdf_path = "stockeasy/local_cache/financial_reports/정기보고서/007660/20240901_이수페타시스_007660_전기·전자_Q3_DART.pdf"

    if not Path(pdf_path).exists():
        logger.warning(f"테스트 PDF 파일이 존재하지 않습니다: {pdf_path}")
        return

    try:
        # 단일 페이지에서 테이블 추출
        target_page = 11
        logger.info("=== 단일 페이지 테이블 추출 테스트 ===")
        tables = extract_tables_from_page(pdf_path, target_page)
        print_table_info(tables, target_page)

        # 설정을 적용한 테이블 추출
        # logger.info("\n=== 설정 적용 테이블 추출 테스트 ===")
        # custom_settings = {"vertical_strategy": "text", "horizontal_strategy": "text"}
        # tables_with_settings = extract_tables_with_settings(pdf_path, 10, custom_settings)
        # print_table_info(tables_with_settings, 10)

        # # 여러 페이지에서 테이블 추출
        # logger.info("\n=== 여러 페이지 테이블 추출 테스트 ===")
        # multi_tables = extract_tables_from_multiple_pages(pdf_path, [8, 9, 10, 11, 12])
        # for page_num, page_tables in multi_tables.items():
        #     print_table_info(page_tables, page_num)

    except Exception as e:
        logger.error(f"테스트 실행 중 오류: {str(e)}")


if __name__ == "__main__":
    test_extract_tables()
