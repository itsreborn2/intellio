"""
리랭커 테스트 예제
"""

import asyncio
import os
import sys
import time
import warnings

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import re  # 정규식 라이브러리

import fitz  # PyMuPDF 라이브러리
import pandas as pd  # DataFrame 라이브러리

# markdown을 html로 변환하는 라이브러리 추가
import pdfplumber
from dotenv import load_dotenv

# LangChain 관련 라이브러리
# OpenAI 모델 임포트 추가
# from langchain_openai import ChatOpenAI
from loguru import logger

from common.core.config import settings

warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
warnings.filterwarnings("ignore", category=UserWarning, module="pdfplumber")
warnings.filterwarnings("ignore", category=UserWarning, module="fitz")  # PyMuPDF 경고 숨기기
warnings.filterwarnings("ignore", message="CropBox missing from /Page, defaulting to MediaBox")

# fitz 라이브러리의 경고 출력 레벨 변경 (0: 모든 출력, 1: 경고만, 2: 오류만, 3: 모두 억제)
# 모든 경고 메시지 억제
fitz.TOOLS.mupdf_warnings_handler = lambda warn_level, message: None

import logging

# # 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력용 핸들러
    ],
)
logger2 = logging.getLogger(__name__)
logger2.setLevel(logging.INFO)  # 명시적으로 INFO 레벨 설정
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# 환경 변수 로드
load_dotenv()
# GEMINI_API_KEY를 사용자가 입력해야 합니다
GEMINI_API_KEY = settings.GEMINI_API_KEY
# OpenAI API 키 설정
OPENAI_API_KEY = settings.OPENAI_API_KEY


async def extract_page_hybrid(page, page_num: int):
    """
    단일 페이지에서 하이브리드 방법으로 테이블과 텍스트를 추출합니다.

    Args:
        page: pdfplumber page 객체
        page_num: 페이지 번호

    Returns:
        str: 추출된 텍스트 (테이블 + 주변 텍스트)
    """
    try:
        page_content = ""
        page_height = page.height

        # 1. 페이지에서 테이블 찾기
        tables = page.find_tables()

        if not tables:
            # 테이블이 없으면 일반 텍스트만 추출
            text = page.extract_text()
            if text:
                page_content += text
            return page_content

        logger.debug(f"페이지 {page_num}에서 {len(tables)} 개의 테이블을 발견했습니다.")

        # 2. 테이블 위치 정보를 수집하고 정렬
        table_positions = []
        for i, table in enumerate(tables):
            bbox = table.bbox  # (x0, y0, x1, y1)
            table_positions.append(
                {
                    "index": i,
                    "table": table,
                    "bbox": bbox,
                    "top": bbox[1],  # y0
                    "bottom": bbox[3],  # y1
                }
            )

        # Y 좌표 기준으로 정렬 (위에서 아래로)
        table_positions.sort(key=lambda x: x["top"])

        # 3. 테이블 사이사이와 주변의 텍스트 추출
        current_y = 0  # 페이지 맨 위부터 시작

        for i, table_info in enumerate(table_positions):
            table = table_info["table"]
            bbox = table_info["bbox"]
            table_top = bbox[1]
            table_bottom = bbox[3]

            # 테이블 위쪽 텍스트 추출 (현재 Y 위치부터 테이블 시작까지)
            if table_top > current_y:
                try:
                    # 테이블 위쪽 영역 크롭
                    text_area_above = page.crop((0, current_y, page.width, table_top))
                    text_above = text_area_above.extract_text()
                    if text_above and text_above.strip():
                        # page_content += f"[테이블 {i + 1} 이전 텍스트]\n{text_above.strip()}\n\n"
                        page_content += f"{text_above.strip()}\n\n"
                except Exception as crop_error:
                    logger.debug(f"테이블 {i + 1} 위쪽 텍스트 추출 오류: {str(crop_error)}")

                    # 테이블 데이터 추출
            try:
                # 방법 1: table 객체의 extract() 메서드 사용 (가장 안정적)
                table_data = table.extract()
                if table_data:
                    page_content += f"[테이블 {i + 1}]\n"
                    for row in table_data:
                        if row and any(cell for cell in row if cell):  # 빈 행이 아닌 경우만
                            # None 값을 빈 문자열로 변환하고 각 셀을 | 로 구분
                            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                            page_content += "| " + " | ".join(cleaned_row) + " |\n"
                    page_content += "\n"
                    logger.debug(f"테이블 {i + 1} 구조화 추출 성공: {len(table_data)} 행")
                else:
                    raise Exception("table.extract() 반환값이 None")
            except Exception as table_error:
                logger.debug(f"테이블 {i + 1} 구조화 추출 오류: {str(table_error)}")
                # 방법 2: 테이블 영역을 텍스트로 추출 (폴백)
                try:
                    table_text_area = page.crop(bbox)
                    table_text = table_text_area.extract_text()
                    if table_text and table_text.strip():
                        page_content += f"[테이블 {i + 1} - 텍스트 형태]\n{table_text.strip()}\n\n"
                        logger.debug(f"테이블 {i + 1} 텍스트 추출 성공: {len(table_text)} 글자")
                    else:
                        logger.warning(f"테이블 {i + 1} 모든 추출 방법 실패")
                except Exception as fallback_error:
                    logger.error(f"테이블 {i + 1} 텍스트 추출도 실패: {str(fallback_error)}")

            # 현재 Y 위치를 테이블 끝으로 업데이트
            current_y = table_bottom

        # 마지막 테이블 아래쪽 텍스트 추출
        if current_y < page_height:
            try:
                text_area_below = page.crop((0, current_y, page.width, page_height))
                text_below = text_area_below.extract_text()
                if text_below and text_below.strip():
                    page_content += f"[마지막 테이블 이후 텍스트]\n{text_below.strip()}\n"
            except Exception as crop_error:
                logger.debug(f"마지막 테이블 아래쪽 텍스트 추출 오류: {str(crop_error)}")

        return page_content

    except Exception as e:
        logger.error(f"페이지 {page_num} 하이브리드 추출 중 오류: {str(e)}")
        # 오류가 발생하면 일반 텍스트 추출로 폴백
        try:
            fallback_text = page.extract_text()
            if fallback_text:
                return f"[폴백 텍스트]\n{fallback_text}\n"
        except Exception as fallback_error:
            logger.error(f"페이지 {page_num} 폴백 텍스트 추출 오류: {str(fallback_error)}")
        return ""


async def extract_revenue_breakdown_data_3(target_report: str):
    """
    Gemini 방식을 도입한 하이브리드 방법으로 사업보고서에서 매출 및 수주 현황 정보를 추출합니다.
    - page.crop().extract_table(settings) 사용
    - 명시적인 테이블 추출 전략 적용
    - pandas DataFrame으로 구조화
    - 단위 정보 추출

    Args:
        target_report: 사업보고서 파일 경로
    return :
        Dict[str, Any]: {
            'text': 텍스트 형태의 추출 결과,
            'tables': [
                {
                    'table_id': int,
                    'page_num': int,
                    'dataframe': pandas.DataFrame,
                    'unit_info': str,
                    'markdown': str
                }
            ],
            'summary': 추출 요약 정보
        }
    """
    doc = None
    try:
        if not os.path.exists(target_report):
            logger.error(f"파일을 찾을 수 없습니다: {target_report}")
            return ""

        base_file_name = os.path.basename(target_report)
        logger.info(f"매출 정보 추출 시작 (Gemini 방식): {base_file_name}")

        year = base_file_name.split("_")[0][:4]
        quater_file = base_file_name.split("_")[4]

        report_type_map = {"Q1": "1Q", "Q3": "3Q", "semiannual": "2Q", "annual": "4Q"}
        quater = report_type_map.get(quater_file, "")

        # fitz를 사용하여 목차 내용 추출
        doc = await asyncio.to_thread(fitz.open, target_report)
        toc = await asyncio.to_thread(doc.get_toc)

        if not toc:
            logger.error("목차를 찾을 수 없습니다.")
            return ""

        # 목차에서 페이지 범위 찾기 (기존 로직과 동일)
        business_content_start_page = None
        business_content_end_page = None
        sales_section_start_page = None
        sales_section_end_page = None
        for i, item in enumerate(toc):
            level, title, page_num = item
            print(f"level: {level}, title: {title}, page_num: {page_num}")

        for i, item in enumerate(toc):
            level, title, page_num = item

            if "사업의 내용" in title and (title.startswith("II.") or title.startswith("Ⅱ.")):
                business_content_start_page = page_num - 1

                for next_item in toc[i + 1 :]:
                    next_level, next_title, next_page = next_item
                    if next_level <= level and (next_title.startswith("III.") or next_title.startswith("Ⅲ.") or next_title.startswith("IV.") or next_title.startswith("Ⅳ.")):
                        business_content_end_page = next_page - 2
                        break

                if business_content_end_page is None:
                    business_content_end_page = len(doc) - 1

            if business_content_start_page is not None and "매출" in title and "수주" in title:
                sales_section_start_page = page_num - 1
                logger.info(f"✅ '매출 및 수주상황' 섹션 발견: '{title}' (L{level}, P{page_num}). 시작 페이지 인덱스: {sales_section_start_page}")

                for next_item in toc[i + 1 :]:
                    next_level, next_title, next_page = next_item
                    logger.info(f"  ➡️ 다음 목차 확인 중: '{next_title}' (L{next_level}, P{next_page})")
                    if next_level <= level:
                        sales_section_end_page = next_page - 1
                        logger.info(f"  ✅ 종료 조건 충족 (next_level({next_level}) <= level({level})). 종료 페이지 인덱스 설정: {next_page} - 1 = {sales_section_end_page}")
                        break
                    else:
                        logger.info(f"  ℹ️ 종료 조건 미충족 (next_level({next_level}) > level({level})). 계속 탐색.")

                if sales_section_end_page is None:
                    sales_section_end_page = business_content_end_page
                    logger.info(f"  ⚠️ 다음 섹션을 찾지 못함. '사업의 내용' 끝 페이지를 사용: {sales_section_end_page}")

        if not business_content_start_page:
            logger.error(f"{year}.{quater}: 'II. 사업의 내용' 섹션을 찾을 수 없습니다.")
            return ""

        # 페이지 범위 결정
        start_page = None
        end_page = None

        if sales_section_start_page is not None and sales_section_end_page is not None:
            start_page = sales_section_start_page
            end_page = sales_section_end_page
            logger.info(f"{year}.{quater}: '매출 및 수주상황' 섹션을 찾았습니다: 페이지 {start_page + 1}~{end_page + 1}")
        elif business_content_start_page is not None and business_content_end_page is not None:
            start_page = business_content_start_page
            end_page = business_content_end_page
            logger.info(f"{year}.{quater}: 'II. 사업의 내용' 섹션을 찾았습니다: 페이지 {start_page + 1}~{end_page + 1}")
        else:
            logger.error(f"{year}.{quater}: 매출 및 수주상황, 사업의 내용 섹션을 찾을 수 없습니다.")
            return ""

        if start_page is None or end_page is None:
            logger.error(f"{year}.{quater}: 유효한 페이지 범위를 결정할 수 없습니다.")
            return ""

        # 추출할 페이지 수 제한
        if end_page - start_page > 30:  # 30페이지 이상이면 제한
            logger.warning(f"{year}.{quater}: 페이지 범위가 너무 큽니다 ({end_page - start_page} 페이지). 30 페이지만 처리합니다.")
            end_page = start_page + 29

        # 결과 저장 구조체 초기화
        result = {"text": "", "tables": [], "summary": {"year": year, "quarter": quater, "total_tables": 0, "total_pages": 0, "page_range": f"{start_page + 1}~{end_page + 1}"}}

        # Gemini 방식으로 페이지 내용 추출
        extracted_text = "-----------------------------\n\n"
        extracted_text += f"## {year}.{quater} 데이터\n"

        try:
            extracted_page_content = ""
            all_page_tables = []  # 모든 페이지의 테이블 정보를 저장

            with pdfplumber.open(target_report) as pdf:
                max_pages = 30
                pdf_length = len(pdf.pages)

                if start_page >= pdf_length:
                    logger.warning(f"시작 페이지({start_page + 1})가 PDF 길이({pdf_length})를 초과합니다")
                    start_page = max(0, pdf_length - 1)

                if end_page >= pdf_length:
                    logger.warning(f"종료 페이지({end_page + 1})가 PDF 길이({pdf_length})를 초과합니다")
                    end_page = pdf_length - 1

                effective_end_page = end_page
                if end_page - start_page > max_pages:
                    logger.warning(f"페이지 범위가 너무 큽니다({start_page + 1}~{end_page + 1}). 처음 {max_pages}페이지만 추출합니다.")
                    effective_end_page = start_page + max_pages

                logger.info(f"{year}.{quater}: 최종 추출 페이지 범위: {start_page + 1}~{effective_end_page + 1}")
                extracted_text += f"### Page : {start_page + 1} ~ {effective_end_page + 1}\n\n"
                result["summary"]["page_range"] = f"{start_page + 1}~{effective_end_page + 1}"
                result["summary"]["total_pages"] = effective_end_page - start_page + 1

                # 1단계: 모든 페이지에서 개별적으로 테이블 추출
                for page_num in range(start_page, effective_end_page + 1):
                    try:
                        page = pdf.pages[page_num]
                        page_result = await extract_page_gemini_style_with_dataframe(page, page_num + 1)

                        if page_result:
                            # 텍스트 결과 누적
                            if page_result["text"]:
                                extracted_page_content += f"{page_result['text']}\n"

                            # 페이지별 테이블 정보 저장
                            if page_result["tables"]:
                                all_page_tables.append({"page_num": page_num + 1, "tables": page_result["tables"]})

                            logger.debug(f"페이지 {page_num + 1} Gemini 방식 추출 완료: 텍스트 {len(page_result['text'])}글자, 테이블 {len(page_result['tables'])}개")
                    except Exception as page_error:
                        logger.error(f"페이지 {page_num + 1} Gemini 방식 추출 오류: {str(page_error)}")

                # 2단계: 페이지 간 테이블 연결성 분석 및 병합
                if all_page_tables:
                    logger.info(f"테이블 연결성 분석 시작: 총 {len(all_page_tables)}개 페이지, {sum(len(pt['tables']) for pt in all_page_tables)}개 테이블")

                    merged_tables = analyze_table_structure_across_pages(all_page_tables)

                    # 병합된 테이블들을 결과에 저장
                    result["tables"] = merged_tables
                    result["summary"]["total_tables"] = len(merged_tables)

                    # 병합된 테이블 정보 로깅
                    for i, table_info in enumerate(merged_tables):
                        pages_info = table_info.get("merged_from_pages", [table_info.get("page_num")])
                        table_count = table_info.get("table_count_in_group", 1)
                        df_shape = table_info.get("dataframe").shape if table_info.get("dataframe") is not None else (0, 0)

                        logger.info(f"병합된 테이블 {i + 1}: 페이지 {pages_info}, {table_count}개 테이블 병합, DataFrame 크기: {df_shape}")

                # 3단계: 최종 텍스트 생성 (병합된 테이블로 원본 텍스트의 테이블 부분 대체)
                if result["tables"]:
                    # 병합된 테이블로 원본 텍스트 재구성 (원본 문서 구조 유지)
                    final_page_content = reconstruct_text_with_merged_tables(extracted_page_content, result["tables"])
                    extracted_text += final_page_content
                else:
                    # 병합된 테이블이 없으면 원본 텍스트 사용
                    extracted_text += extracted_page_content

        except Exception as pdf_error:
            logger.exception(f"PDF Gemini 방식 처리 중 오류: {str(pdf_error)}")

        # extracted_text += f"\n\n</{year}.{quater} 데이터>\n"
        result["text"] = extracted_text

        if not extracted_page_content or not extracted_page_content.strip():
            logger.error("추출된 텍스트가 없습니다.")
            return ""

        logger.info(f"Gemini 방식 텍스트 추출 완료: {len(extracted_text)} 글자, {result['summary']['total_tables']} 테이블 (병합 후), {result['summary']['total_pages']} 페이지")
        return result

    except Exception as e:
        logger.exception(f"Error extracting revenue breakdown data (Gemini style): {str(e)}")
        return ""

    finally:
        if doc is not None:
            try:
                doc.close()
                logger.debug("PDF 문서 리소스 해제 완료")
            except Exception as close_error:
                logger.error(f"PDF 문서 리소스 해제 오류: {str(close_error)}")


def extract_unit_info(text: str) -> str:
    """
    텍스트에서 단위 정보를 추출합니다.

    Args:
        text: 텍스트

    Returns:
        str: 추출된 단위 정보 (예: "단위: 원", "단위: 십억원, USD")
    """
    if not text:
        return ""

    # 단위 정보를 찾는 정규식 패턴들
    unit_patterns = [
        r"\(단위[:\s]*([^)]+)\)",  # (단위: 원), (단위 : 십억원, USD)
        r"단위[:\s]*([^,\n\r]+)",  # 단위: 원, 단위 : 십억원
        r"\[단위[:\s]*([^\]]+)\]",  # [단위: 원]
        r"<단위[:\s]*([^>]+)>",  # <단위: 원>
    ]

    for pattern in unit_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # 가장 첫 번째 매치 반환, 앞뒤 공백 제거
            unit = matches[0].strip()
            return f"단위: {unit}"

    return ""


def parse_unit_to_multiplier(unit_str: str) -> float:
    """
    단위 문자열을 배수로 변환합니다.

    Args:
        unit_str: 단위 문자열 (예: "백만원", "십억원", "조원")

    Returns:
        float: 배수 (예: 백만원 -> 1000000, 십억원 -> 1000000000)
    """
    if not unit_str:
        return 1.0

    unit_str = unit_str.lower().strip()

    # 단위 매핑 (긴 단위부터 매칭하기 위해 길이 순으로 정렬)
    unit_multipliers = {
        "십조원": 10000000000000,
        "조원": 1000000000000,
        "천억원": 100000000000,
        "백억원": 10000000000,
        "십억원": 1000000000,
        "억원": 100000000,
        "천만원": 10000000,
        "백만원": 1000000,
        "십만원": 100000,
        "만원": 10000,
        "천원": 1000,
        "백원": 100,
        "십원": 10,
        "원": 1,
        # 영어 단위
        "trillion": 1000000000000,
        "billion": 1000000000,
        "million": 1000000,
    }

    # 길이가 긴 단위부터 매칭 (정확한 매칭을 위해)
    for unit, multiplier in unit_multipliers.items():
        if unit in unit_str:
            return multiplier

    return 1.0


def replace_unit_in_text(original_text: str, old_unit_name: str, new_unit_name: str) -> str:
    """
    텍스트 내에서 '단위:'와 같은 키워드가 포함된 줄의 단위만 교체합니다.
    예: (단위 : 백만원) -> (단위 : 십억원)

    Args:
        original_text (str): 원본 텍스트.
        old_unit_name (str): 교체될 기존 단위 이름 (예: "백만원").
        new_unit_name (str): 새로 적용될 단위 이름 (예: "십억원").

    Returns:
        str: 단위가 교체된 텍스트.
    """
    if not all([original_text, old_unit_name, new_unit_name]):
        return original_text

    lines = original_text.split("\n")
    new_lines = []
    for line in lines:
        # '단위' 키워드가 있는 줄에서만 교체를 시도하여 오탐을 방지합니다.
        if "단위" in line:
            new_lines.append(line.replace(old_unit_name, new_unit_name))
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def is_numeric_value(value: str) -> bool:
    """
    문자열이 숫자 값인지 확인합니다.

    Args:
        value: 확인할 문자열

    Returns:
        bool: 숫자 값 여부
    """
    if not isinstance(value, str):
        logger.debug(f"is_numeric_value: 잘못된 입력 타입 - {value} ({type(value)})")
        return False

    # 공백 제거
    value = value.strip()

    # 빈 문자열 체크
    if not value:
        # logger.debug("is_numeric_value: 빈 문자열")
        return False

    # 퍼센트 기호가 있으면 숫자가 아님
    if "%" in value:
        # logger.debug(f"is_numeric_value: 퍼센트 값 - {value}")
        return False

    # 쉼표 제거하고 숫자 확인
    clean_value = value.replace(",", "").replace("(", "").replace(")", "")

    # 음수 처리 (괄호 또는 마이너스)
    if value.startswith("(") and value.endswith(")"):
        clean_value = "-" + clean_value
    elif clean_value.startswith("-"):
        pass

    try:
        float(clean_value)
        # logger.debug(f"is_numeric_value: 숫자 인식 성공 - {value} -> {clean_value}")
        return True
    except ValueError:
        # logger.debug(f"is_numeric_value: 숫자 인식 실패 - {value}")
        return False


def convert_value_to_target_unit(value: str, source_multiplier: float, target_multiplier: float) -> str:
    """
    값을 소스 단위에서 타겟 단위로 변환합니다.

    Args:
        value: 변환할 값 (문자열)
        source_multiplier: 소스 단위의 배수
        target_multiplier: 타겟 단위의 배수

    Returns:
        str: 변환된 값 (문자열)
    """

    # logger.debug(f"convert_value_to_target_unit 시작: value='{value}', source_multiplier={source_multiplier}, target_multiplier={target_multiplier}")

    if not is_numeric_value(value):
        # logger.debug(f"convert_value_to_target_unit: 숫자가 아님, 원본 반환 - '{value}'")
        return value

    try:
        # 쉼표 제거 및 괄호 처리
        clean_value = value.replace(",", "")
        is_negative = False

        if clean_value.startswith("(") and clean_value.endswith(")"):
            clean_value = clean_value[1:-1]
            is_negative = True
        elif clean_value.startswith("-"):
            is_negative = True
            clean_value = clean_value[1:]

        # logger.debug(f"convert_value_to_target_unit: clean_value='{clean_value}', is_negative={is_negative}")

        # 숫자로 변환
        numeric_value = float(clean_value)

        # 음수 처리
        if is_negative:
            numeric_value = -numeric_value

        # logger.debug(f"convert_value_to_target_unit: numeric_value={numeric_value}")

        # 단위 변환
        converted_value = numeric_value * source_multiplier / target_multiplier

        # logger.debug(f"convert_value_to_target_unit: converted_value={converted_value} (계산: {numeric_value} * {source_multiplier} / {target_multiplier})")

        # 포맷팅
        if converted_value == 0:
            formatted = "0"
        elif abs(converted_value) >= 1:
            # 소수점 2자리까지 표시, 불필요한 0 제거
            formatted = f"{converted_value:,.2f}".rstrip("0").rstrip(".")
        else:
            # 1보다 작은 경우 소수점 4자리까지
            formatted = f"{converted_value:.4f}".rstrip("0").rstrip(".")

        # logger.debug(f"convert_value_to_target_unit: 변환 완료 '{value}' -> '{formatted}'")
        return formatted

    except Exception as e:
        logger.debug(f"convert_value_to_target_unit: 변환 오류 {value} -> {str(e)}")
        return value


def convert_dataframe_units(df: pd.DataFrame, source_unit: str, target_unit: str = "십억원") -> pd.DataFrame:
    """
    DataFrame의 숫자 데이터를 다른 단위로 변환합니다.

    Args:
        df: 변환할 DataFrame
        source_unit: 소스 단위 정보 (예: "단위: 백만원")
        target_unit: 타겟 단위 (예: "십억원")

    Returns:
        pd.DataFrame: 단위가 변환된 DataFrame
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    # 소스 단위에서 실제 단위 추출
    source_unit_clean = source_unit.replace("단위:", "").replace("단위 :", "").strip()
    if "," in source_unit_clean:
        # 여러 단위가 있는 경우 첫 번째 사용
        source_unit_clean = source_unit_clean.split(",")[0].strip()

    # 단위 배수 계산
    source_multiplier = parse_unit_to_multiplier(source_unit_clean)
    target_multiplier = parse_unit_to_multiplier(target_unit)

    logger.debug(f"단위 변환: {source_unit_clean} ({source_multiplier:,}) -> {target_unit} ({target_multiplier:,})")

    # pandas DataFrame의 완전한 복사 (새로운 독립 객체 생성)
    converted_df = pd.DataFrame(df.values.copy(), columns=df.columns.copy(), index=df.index.copy())

    logger.debug(f"변환 시작 - 원본 DataFrame 크기: {df.shape}")
    logger.debug(f"변환용 DataFrame ID: {id(converted_df)}, 원본 DataFrame ID: {id(df)}")
    logger.debug(f"DataFrame 독립성 확인: {id(converted_df) != id(df)}")

    # 각 셀에 대해 변환 수행
    conversion_count = 0
    for col in converted_df.columns:
        for idx in converted_df.index:
            original_value = converted_df.at[idx, col]
            if pd.isna(original_value) or original_value == "":
                continue

            original_str = str(original_value)
            converted_value = convert_value_to_target_unit(original_str, source_multiplier, target_multiplier)

            # 변환이 실제로 발생했는지 확인
            if converted_value != original_str:
                conversion_count += 1
                # logger.debug(f"셀 변환: [{idx}, '{col}'] '{original_str}' -> '{converted_value}'")

                # 실제 DataFrame에 값 할당
                converted_df.at[idx, col] = converted_value

                # 할당 후 값 확인
                assigned_value = converted_df.at[idx, col]
                # logger.debug(f"할당 확인: [{idx}, '{col}'] 설정값: '{converted_value}' 실제값: '{assigned_value}'")

    logger.debug(f"총 {conversion_count}개 셀이 변환되었습니다.")

    # 변환 완료 후 샘플 값 확인
    if conversion_count > 0:
        sample_row = 0
        for col in converted_df.columns:
            val = converted_df.at[sample_row, col] if sample_row < len(converted_df) else None
            if val and is_numeric_value(str(val)):
                logger.debug(f"변환 완료 샘플 확인: [{sample_row}, '{col}'] = '{val}'")
                break

    # 메타데이터 업데이트
    converted_df.attrs["original_unit"] = source_unit
    converted_df.attrs["converted_unit"] = f"단위: {target_unit}"

    # 최종 검증: 변환이 제대로 적용되었는지 확인
    logger.debug("=== 변환 결과 최종 검증 ===")
    verification_count = 0
    for col in converted_df.columns:
        for idx in converted_df.index:
            current_value = converted_df.at[idx, col]
            if current_value and is_numeric_value(str(current_value)):
                original_in_df = df.at[idx, col] if idx in df.index and col in df.columns else None
                logger.debug(f"검증: [{idx}, '{col}'] 원본='{original_in_df}' 현재='{current_value}'")
                verification_count += 1
                if verification_count >= 3:  # 처음 3개만 검증
                    break
        if verification_count >= 3:
            break
    logger.debug("=== 검증 완료 ===")

    return converted_df


def dataframe_to_markdown(df: pd.DataFrame, table_id: int = 1) -> str:
    """
    DataFrame을 마크다운 테이블로 변환합니다.

    Args:
        df: 변환할 DataFrame
        table_id: 테이블 ID

    Returns:
        str: 마크다운 형태의 테이블 문자열
    """
    if df.empty:
        return f"[테이블 {table_id} - 빈 테이블]\n\n"

    markdown_content = ""

    # 단위 정보가 있으면 추가
    # converted_unit = df.attrs.get("converted_unit", "")
    # if converted_unit:
    #     markdown_content += f"**{converted_unit}**\n\n"

    # 컬럼 헤더 추가
    if not df.columns.empty and len(df.columns) > 0:
        header_row = []
        for col in df.columns:
            header_row.append(str(col) if col and str(col).strip() else "")
        markdown_content += "| " + " | ".join(header_row) + " |\n"

        # 구분선 추가
        separator = ["---"] * len(header_row)
        markdown_content += "| " + " | ".join(separator) + " |\n"

    # 데이터 행 추가
    for idx, row in df.iterrows():
        row_data = []
        for value in row:
            if pd.isna(value) or value == "":
                row_data.append("")
            else:
                clean_value = str(value).strip()
                row_data.append(clean_value)

        # 빈 행이 아닌 경우만 추가
        if any(cell for cell in row_data if cell):
            markdown_content += "| " + " | ".join(row_data) + " |\n"

    markdown_content += "\n"
    return markdown_content


def create_dataframe_from_table(table_data: list, unit_info: str = ""):
    """
    테이블 데이터를 pandas DataFrame으로 변환합니다.

    Args:
        table_data: 2차원 리스트 형태의 테이블 데이터
        unit_info: 단위 정보

    Returns:
        pandas.DataFrame: 변환된 DataFrame
    """
    if not table_data or len(table_data) == 0:
        return pd.DataFrame()

    try:
        # 빈 행 제거
        cleaned_data = []
        for row in table_data:
            if row and any(cell for cell in row if cell and str(cell).strip()):
                # None 값을 빈 문자열로 변환하고 각 셀 정리
                cleaned_row = []
                for cell in row:
                    if cell:
                        clean_cell = str(cell).strip().replace("\n", " ").replace("\r", "")
                        clean_cell = " ".join(clean_cell.split())
                        cleaned_row.append(clean_cell)
                    else:
                        cleaned_row.append("")
                cleaned_data.append(cleaned_row)

        if not cleaned_data:
            return pd.DataFrame()

        # DataFrame 생성
        df = pd.DataFrame(cleaned_data)

        # 첫 번째 행을 컬럼명으로 사용 (헤더가 있는 경우)
        if len(cleaned_data) > 1:
            # 첫 번째 행이 헤더인지 판단 (숫자가 적고 의미있는 텍스트가 많으면 헤더로 간주)
            first_row = cleaned_data[0]
            numeric_count = sum(1 for cell in first_row if cell and str(cell).replace(",", "").replace(".", "").replace("-", "").isdigit())
            meaningful_text_count = sum(1 for cell in first_row if cell and len(str(cell).strip()) > 2 and not is_numeric_value(str(cell)))

            # 헤더 판단 조건을 더 엄격하게: 숫자 비율이 낮고 의미있는 텍스트가 있어야 함
            numeric_ratio = numeric_count / len(first_row) if len(first_row) > 0 else 0
            meaningful_ratio = meaningful_text_count / len(first_row) if len(first_row) > 0 else 0

            is_header = numeric_ratio < 0.4 and meaningful_ratio > 0.3  # 더 엄격한 조건

            if is_header:
                # 컬럼명 설정 및 중복 처리
                header = list(first_row)
                new_header = []
                counts = {}
                for col in header:
                    clean_col = col if col and str(col).strip() else "Unnamed"
                    if clean_col in counts:
                        counts[clean_col] += 1
                        new_header.append(f"{clean_col}.{counts[clean_col]}")
                    else:
                        counts[clean_col] = 1
                        new_header.append(clean_col)

                df.columns = new_header
                df = df.iloc[1:].reset_index(drop=True)
                logger.debug(f"DataFrame 생성: 첫 행을 헤더로 설정 (숫자비율: {numeric_ratio:.2f}, 텍스트비율: {meaningful_ratio:.2f})")
            else:
                logger.debug(f"DataFrame 생성: 첫 행을 데이터로 유지 (숫자비율: {numeric_ratio:.2f}, 텍스트비율: {meaningful_ratio:.2f})")

        # 단위 정보가 있으면 DataFrame에 메타데이터로 추가
        if unit_info:
            df.attrs["unit_info"] = unit_info

        return df

    except Exception as e:
        logger.error(f"DataFrame 생성 중 오류: {str(e)}")
        return pd.DataFrame()


def _clean_extracted_text(text: str) -> str:
    """
    추출된 텍스트에서 불필요한 라인을 제거합니다.

    Args:
        text: 정리할 텍스트

    Returns:
        str: 정리된 텍스트
    """
    if not text:
        return text

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        # '전자공시시스템 dart.fss.or.kr' 문구가 있는 라인 제거
        if "전자공시시스템 dart.fss.or.kr" in line:
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def is_position_based_continuation(prev_table_info: dict, current_table_info: dict) -> bool:
    """
    좌표 기반으로 테이블 연속성을 판단합니다 (레이아웃 인식 기반 분석).

    페이지 간 연속성뿐만 아니라 같은 페이지 내에서도 물리적 거리를 고려합니다.

    Args:
        prev_table_info: 이전 테이블 정보 (bbox 포함)
        current_table_info: 현재 테이블 정보 (bbox 포함)

    Returns:
        bool: 위치상 연속된 테이블인지 여부
    """
    if not prev_table_info or not current_table_info:
        return False

    prev_bbox = prev_table_info.get("bbox")
    curr_bbox = current_table_info.get("bbox")
    prev_page = prev_table_info.get("page_num")
    curr_page = current_table_info.get("page_num")
    prev_pos = prev_table_info.get("table_position_in_page", 0)
    curr_pos = current_table_info.get("table_position_in_page", 0)

    if not prev_bbox or not curr_bbox or not prev_page or not curr_page:
        return False

    prev_bottom = prev_bbox[3]  # 이전 테이블 하단 Y좌표
    curr_top = curr_bbox[1]  # 현재 테이블 상단 Y좌표
    page_height = 792  # 일반적인 A4 페이지 높이

    # 케이스 1: 페이지 간 연속성 (기존 로직)
    if curr_page - prev_page == 1:
        # 현재 페이지의 첫 번째 테이블이어야 함
        if curr_pos != 0:
            return False

        # 이전 테이블이 페이지 하단 70% 이후에 있고
        # 현재 테이블이 페이지 상단 30% 이전에 있으면 연속성 높음
        prev_near_bottom = prev_bottom > (page_height * 0.7)
        curr_near_top = curr_top < (page_height * 0.3)

        is_continuous = prev_near_bottom and curr_near_top

        if is_continuous:
            logger.debug(f"[페이지간] 좌표 기반 연속성 감지: 이전 테이블 하단={prev_bottom:.1f}, 현재 테이블 상단={curr_top:.1f}")

        return is_continuous

    # 케이스 2: 같은 페이지 내 물리적 거리 분석 (새로운 로직)
    elif curr_page == prev_page:
        # 테이블 간 수직 거리 계산
        vertical_gap = curr_top - prev_bottom

        # 최소 허용 거리 (페이지 높이의 5% = 약 40포인트)
        min_allowed_gap = page_height * 0.05

        # 최대 허용 거리 (페이지 높이의 15% = 약 120포인트)
        max_allowed_gap = page_height * 0.15

        # 거리 기반 연속성 판단
        is_continuous_distance = min_allowed_gap <= vertical_gap <= max_allowed_gap

        # 추가 조건: 테이블이 연속된 순서여야 함
        is_consecutive_position = curr_pos == prev_pos + 1

        is_continuous = is_continuous_distance and is_consecutive_position

        if is_continuous:
            logger.debug(f"[페이지내] 좌표 기반 연속성 감지: 수직거리={vertical_gap:.1f}포인트 (허용범위: {min_allowed_gap:.1f}~{max_allowed_gap:.1f})")
        else:
            logger.debug(f"[페이지내] 좌표 기반 연속성 거부: 수직거리={vertical_gap:.1f}포인트, 연속위치={is_consecutive_position}")

        return is_continuous

    # 케이스 3: 페이지가 2개 이상 떨어져 있으면 연속성 없음
    else:
        return False


def is_table_continuation(prev_table_df: pd.DataFrame, current_table_df: pd.DataFrame, similarity_threshold: float = 0.4) -> bool:
    """
    이전 테이블과 현재 테이블이 연결된 테이블인지 판단합니다.

    Args:
        prev_table_df: 이전 페이지의 마지막 테이블 DataFrame
        current_table_df: 현재 페이지의 첫 번째 테이블 DataFrame
        similarity_threshold: 컬럼 유사도 임계값

    Returns:
        bool: 테이블이 연결되는지 여부
    """
    if prev_table_df is None or current_table_df is None or prev_table_df.empty or current_table_df.empty:
        return False

    # 1. 컬럼 개수 확인 (더 유연하게)
    prev_col_count = len(prev_table_df.columns)
    curr_col_count = len(current_table_df.columns)

    # 매출 테이블의 경우 합계 테이블은 컬럼이 1개 적을 수 있음 (매출유형 컬럼 제외)
    col_diff = abs(prev_col_count - curr_col_count)

    # 컬럼 개수 차이가 2개 이상이면 일단 거부
    if col_diff > 2:
        logger.debug(f"테이블 연결 판단: 컬럼 개수 차이가 너무 큼 - 이전:{prev_col_count}, 현재:{curr_col_count}")
        return False

    # 2. 컬럼명 유사도 계산 (레이아웃 인식 기반 개선)
    prev_columns = [str(col).strip().lower() for col in prev_table_df.columns]
    current_columns = [str(col).strip().lower() for col in current_table_df.columns]

    # 더 짧은 컬럼 리스트 기준으로 비교
    min_col_count = min(len(prev_columns), len(current_columns))
    similar_count = 0
    unnamed_count = 0  # 의미없는 컬럼 개수 추적

    def is_meaningless_column(col_name: str) -> bool:
        """의미없는 컬럼명인지 판단 (Unnamed, 숫자, 빈 문자열 등)"""
        if not col_name or not col_name.strip():
            return True
        if "unnamed" in col_name:
            return True
        # 숫자로만 이루어진 컬럼명도 의미없는 것으로 간주
        if col_name.isdigit():
            return True
        # 매우 짧은 컬럼명 (1~2자)도 의미없는 것으로 간주
        if len(col_name.strip()) <= 2:
            return True
        return False

    for i in range(min_col_count):
        prev_col = prev_columns[i] if i < len(prev_columns) else ""
        curr_col = current_columns[i] if i < len(current_columns) else ""

        prev_meaningless = is_meaningless_column(prev_col)
        curr_meaningless = is_meaningless_column(curr_col)

        if prev_col == curr_col and not prev_meaningless:  # 의미있는 컬럼명이 같은 경우
            similar_count += 1
        elif prev_meaningless and curr_meaningless:
            unnamed_count += 1  # 의미없는 컬럼 개수만 추적
        elif prev_col and curr_col and not prev_meaningless and not curr_meaningless:
            if prev_col in curr_col or curr_col in prev_col:
                similar_count += 0.7
        elif prev_meaningless or curr_meaningless:
            unnamed_count += 1  # 한 쪽이라도 의미없으면 카운트

    # 의미없는 컬럼이 대부분인 경우 유사도 계산 방식 변경
    unnamed_ratio = unnamed_count / min_col_count if min_col_count > 0 else 0

    if unnamed_ratio > 0.7:  # 70% 이상이 의미없는 컬럼이면
        # 의미있는 컬럼명만으로 유사도 계산 (더 엄격한 기준)
        meaningful_col_count = min_col_count - unnamed_count
        if meaningful_col_count > 0:
            similarity_ratio = similar_count / meaningful_col_count
            logger.debug(f"테이블 연결 판단: 의미없는 컬럼 비율 높음({unnamed_ratio:.2f}), 의미있는 컬럼만으로 계산: {similarity_ratio:.2f}")
        else:
            # 모든 컬럼이 의미없으면 매우 낮은 유사도 부여
            similarity_ratio = 0.1
            logger.debug(f"테이블 연결 판단: 모든 컬럼이 의미없음 (숫자/Unnamed), 낮은 유사도 부여: {similarity_ratio:.2f}")
    else:
        # 일반적인 경우: 의미없는 컬럼도 부분적으로 반영 (0.3 가중치)
        similarity_ratio = (similar_count + unnamed_count * 0.3) / min_col_count

    logger.debug(f"테이블 연결 판단: 컬럼 유사도 {similarity_ratio:.2f} (임계값: {similarity_threshold}, 의미없음비율: {unnamed_ratio:.2f})")

    # 3. 현재 테이블의 첫 번째 행이 헤더인지 확인 (관대한 조건)
    header_penalty = 0
    if len(current_table_df) > 0:
        first_row = current_table_df.iloc[0]
        numeric_count = sum(1 for val in first_row if val and is_numeric_value(str(val)))
        if len(first_row) > 0:
            numeric_ratio = numeric_count / len(first_row)
            if numeric_ratio < 0.2:  # 20% 미만이 숫자면 헤더일 가능성 높음
                header_penalty = 0.2
                logger.debug(f"테이블 연결 판단: 현재 테이블의 첫 행이 헤더일 가능성 (숫자 비율: {numeric_ratio:.2f}, 페널티: {header_penalty})")

    # 4. 매출 테이블 특별 처리
    revenue_keywords = ["매출", "수출", "내수", "소계", "합계", "총계", "사업부문", "판매", "구분"]
    keyword_bonus = 0
    revenue_table_bonus = 0

    # 이전 테이블과 현재 테이블에서 매출 관련 키워드 확인
    prev_text = " ".join([str(col) for col in prev_table_df.columns]) + " " + " ".join([str(val) for val in prev_table_df.iloc[0] if len(prev_table_df) > 0])
    curr_text = " ".join([str(col) for col in current_table_df.columns]) + " " + " ".join([str(val) for val in current_table_df.iloc[0] if len(current_table_df) > 0])

    # 기본 키워드 매칭
    for keyword in revenue_keywords:
        if keyword in prev_text and keyword in curr_text:
            keyword_bonus += 0.1

    # 최대 0.3까지 보너스
    keyword_bonus = min(keyword_bonus, 0.3)
    if keyword_bonus > 0:
        logger.debug(f"테이블 연결 판단: 매출 키워드 보너스 {keyword_bonus:.2f}")

    # 5. 매출 테이블 → 합계 테이블 패턴 감지
    is_prev_revenue_table = any(keyword in prev_text for keyword in ["매출유형", "품 목", "사업부문"])
    is_curr_summary_table = False

    if len(current_table_df) > 0:
        # 현재 테이블이 합계성 테이블인지 확인
        curr_first_row = current_table_df.iloc[0]
        curr_all_text = " ".join([str(val) for val in curr_first_row if val and str(val).strip()])

        # 합계 패턴 감지: "합 계", "합계", "Total" 등
        summary_patterns = ["합 계", "합계", "총계", "total", "계"]
        is_curr_summary_table = any(pattern in curr_all_text.lower() for pattern in summary_patterns)

        # 현재 테이블의 데이터 패턴이 매출 데이터와 유사한지 확인
        if is_curr_summary_table:
            # 컬럼명이 숫자로 되어있고, 데이터가 수출/내수/합계 패턴인지 확인
            has_export_import_pattern = any(
                "수출" in str(val) or "내수" in str(val) or "합계" in str(val) for _, row in current_table_df.iterrows() for val in row if val and str(val).strip()
            )

            if has_export_import_pattern:
                revenue_table_bonus = 0.5  # 강력한 보너스
                logger.debug(f"테이블 연결 판단: 매출→합계 테이블 패턴 감지 (보너스: {revenue_table_bonus})")

    # 6. 컬럼 구조 호환성 검사 (매출 테이블 특별 케이스)
    column_structure_bonus = 0
    if is_prev_revenue_table and col_diff == 1:
        # 이전 테이블이 매출 테이블이고 현재 테이블의 컬럼이 1개 적으면
        # 첫 번째 컬럼(매출유형)이 제외된 합계 테이블일 가능성 높음

        # 현재 테이블의 숫자 컬럼들이 이전 테이블의 마지막 컬럼들과 매칭되는지 확인
        if len(current_table_df.columns) >= 3:  # 최소 3개 컬럼 (구분, 연도1, 연도2)
            # 현재 테이블에 연도 정보가 있는지 확인
            year_patterns = ["2025", "2024", "2023", "연결기준", "분기", "기"]
            curr_has_years = any(any(pattern in str(val) for pattern in year_patterns) for _, row in current_table_df.iterrows() for val in row if val)

            if curr_has_years:
                column_structure_bonus = 0.3
                logger.debug(f"테이블 연결 판단: 매출 테이블 구조 호환성 감지 (보너스: {column_structure_bonus})")

    # 5. 특별 케이스: 페이지 간 테이블 분할로 헤더가 사라진 경우 감지
    page_split_bonus = 0

    # 컬럼 개수가 같고, 현재 테이블의 첫 행에 숫자가 많으면 데이터 연속 가능성 높음
    if len(prev_table_df.columns) == len(current_table_df.columns) and len(current_table_df) > 0:
        first_row = current_table_df.iloc[0]
        numeric_count = sum(1 for val in first_row if val and is_numeric_value(str(val)))
        numeric_ratio = numeric_count / len(first_row) if len(first_row) > 0 else 0

        # 이전 테이블이 매출 관련이고, 현재 테이블 첫 행이 대부분 숫자면 연속 가능성 높음
        if numeric_ratio > 0.4:  # 40% 이상이 숫자
            prev_last_rows = prev_table_df.tail(3)  # 마지막 3행 확인
            prev_has_revenue_data = any(
                "매출" in str(val) or "수출" in str(val) or "내수" in str(val) or "소계" in str(val) for _, row in prev_last_rows.iterrows() for val in row if val
            )

            if prev_has_revenue_data:
                page_split_bonus = 0.4  # 강력한 보너스
                logger.debug(f"테이블 연결 판단: 페이지 분할 케이스 감지 (숫자 비율: {numeric_ratio:.2f}, 보너스: {page_split_bonus})")

        # 추가: 이전 테이블 마지막 행과 현재 테이블 첫 행의 패턴 유사성 검사
        if len(prev_table_df) > 0:
            prev_last_row = prev_table_df.iloc[-1]
            curr_first_row = current_table_df.iloc[0]

            # 두 행의 숫자 패턴이 유사한지 확인 (같은 위치에 숫자가 있는지)
            pattern_match = 0
            for i, (prev_val, curr_val) in enumerate(zip(prev_last_row, curr_first_row)):
                prev_is_num = is_numeric_value(str(prev_val))
                curr_is_num = is_numeric_value(str(curr_val))
                if prev_is_num and curr_is_num:
                    pattern_match += 1
                elif not prev_is_num and not curr_is_num and str(prev_val).strip() and str(curr_val).strip():
                    pattern_match += 0.5

            pattern_ratio = pattern_match / len(prev_last_row) if len(prev_last_row) > 0 else 0
            if pattern_ratio > 0.5:  # 50% 이상 패턴 일치
                page_split_bonus = max(page_split_bonus, 0.3)
                logger.debug(f"테이블 연결 판단: 행 패턴 유사성 감지 (패턴 비율: {pattern_ratio:.2f})")

    final_similarity = similarity_ratio + keyword_bonus + page_split_bonus + revenue_table_bonus + column_structure_bonus - header_penalty
    logger.debug(
        f"테이블 연결 판단: 최종 유사도 {final_similarity:.2f} (기본: {similarity_ratio:.2f}, 키워드: {keyword_bonus:.2f}, 페이지분할: {page_split_bonus:.2f}, 매출합계: {revenue_table_bonus:.2f}, 구조호환: {column_structure_bonus:.2f}, 헤더페널티: {header_penalty:.2f})"
    )

    return final_similarity >= similarity_threshold


def merge_continued_tables(prev_table_df: pd.DataFrame, current_table_df: pd.DataFrame) -> pd.DataFrame:
    """
    연결된 테이블을 병합합니다.

    Args:
        prev_table_df: 이전 테이블 DataFrame
        current_table_df: 현재 테이블 DataFrame

    Returns:
        pd.DataFrame: 병합된 DataFrame
    """
    if prev_table_df is None or prev_table_df.empty:
        return current_table_df

    if current_table_df is None or current_table_df.empty:
        return prev_table_df

    try:
        # 현재 테이블의 첫 번째 행이 헤더인지 다시 한 번 확인
        current_df_to_merge = current_table_df.copy()

        if len(current_df_to_merge) > 0:
            first_row = current_df_to_merge.iloc[0]
            # 이전 테이블의 컬럼명과 현재 테이블의 첫 행을 비교
            prev_columns = [str(col).strip().lower() for col in prev_table_df.columns]
            first_row_values = [str(val).strip().lower() if val else "" for val in first_row]

            # 헤더 유사도 계산
            header_similarity = sum(
                1 for prev_col, curr_val in zip(prev_columns, first_row_values) if prev_col and curr_val and (prev_col == curr_val or prev_col in curr_val or curr_val in prev_col)
            )

            # 현재 행이 실제 데이터인지 확인 (숫자가 많으면 데이터 행일 가능성 높음)
            numeric_count = sum(1 for val in first_row if val and is_numeric_value(str(val)))
            numeric_ratio = numeric_count / len(first_row) if len(first_row) > 0 else 0

            # 헤더 판단 조건을 더 엄격하게
            is_likely_header = header_similarity >= len(prev_columns) * 0.5 and numeric_ratio < 0.3

            if is_likely_header:
                logger.debug(f"테이블 병합: 현재 테이블의 첫 행을 헤더로 인식하여 제거 (헤더유사도: {header_similarity}/{len(prev_columns)}, 숫자비율: {numeric_ratio:.2f})")
                current_df_to_merge = current_df_to_merge.iloc[1:].reset_index(drop=True)
            else:
                logger.debug(f"테이블 병합: 현재 테이블의 첫 행을 데이터로 유지 (헤더유사도: {header_similarity}/{len(prev_columns)}, 숫자비율: {numeric_ratio:.2f})")

        # 컬럼명 통일 처리
        if len(prev_table_df.columns) == len(current_df_to_merge.columns):
            # 컬럼 개수가 같으면 이전 테이블 컬럼명 사용
            current_df_to_merge.columns = prev_table_df.columns
        elif abs(len(prev_table_df.columns) - len(current_df_to_merge.columns)) == 1:
            # 컬럼 개수가 1개 차이나는 경우 (매출 테이블 → 합계 테이블)
            if len(prev_table_df.columns) > len(current_df_to_merge.columns):
                # 이전 테이블이 더 많은 컬럼을 가진 경우 (매출유형 컬럼 제외)
                # 이전 테이블의 마지막 N개 컬럼명을 현재 테이블에 적용
                target_columns = list(prev_table_df.columns[-len(current_df_to_merge.columns) :])

                # 첫 번째 컬럼을 적절히 조정 (매출유형 → 구분 등)
                if len(target_columns) > 0:
                    # 현재 테이블의 첫 번째 컬럼이 숫자가 아닌 의미있는 데이터가 있으면
                    first_col_data = current_df_to_merge.iloc[:, 0].dropna().astype(str)
                    if any("합" in val or "계" in val or "total" in val.lower() for val in first_col_data):
                        target_columns[0] = "구분"  # 합계 테이블의 첫 컬럼은 보통 '구분'
                    else:
                        target_columns[0] = "항목"  # 일반적인 경우

                current_df_to_merge.columns = target_columns
                logger.debug(f"테이블 병합: 컬럼명 조정 완료 - {target_columns}")
            else:
                # 현재 테이블이 더 많은 컬럼을 가진 경우 (현재 테이블 컬럼명 유지)
                logger.debug(f"테이블 병합: 현재 테이블 컬럼명 유지 - {list(current_df_to_merge.columns)}")
        else:
            logger.debug(f"테이블 병합: 컬럼 개수 차이가 커서 컬럼명 통일 건너뜀 - 이전:{len(prev_table_df.columns)}, 현재:{len(current_df_to_merge.columns)}")

        # DataFrame 병합 (컬럼 개수가 다른 경우 처리)
        if len(prev_table_df.columns) == len(current_df_to_merge.columns):
            # 컬럼 개수가 같으면 일반 병합
            merged_df = pd.concat([prev_table_df, current_df_to_merge], ignore_index=True)
        else:
            # 컬럼 개수가 다른 경우 빈 컬럼으로 채워서 병합
            # 더 많은 컬럼을 가진 쪽에 맞춤
            max_cols = max(len(prev_table_df.columns), len(current_df_to_merge.columns))

            if len(prev_table_df.columns) < max_cols:
                # 이전 테이블에 컬럼 추가
                for i in range(max_cols - len(prev_table_df.columns)):
                    prev_table_df[f"추가컬럼_{i}"] = ""

            if len(current_df_to_merge.columns) < max_cols:
                # 현재 테이블에 컬럼 추가 (앞쪽에 추가 - 매출유형 컬럼 자리)
                missing_cols = max_cols - len(current_df_to_merge.columns)
                for i in range(missing_cols):
                    col_name = f"매출유형_{i}" if i == 0 else f"추가컬럼_{i}"
                    current_df_to_merge.insert(0, col_name, "")

                # 컬럼명 다시 맞춤
                current_df_to_merge.columns = prev_table_df.columns

            merged_df = pd.concat([prev_table_df, current_df_to_merge], ignore_index=True)
            logger.debug(f"테이블 병합: 컬럼 개수 조정 후 병합 완료 - 최종 컬럼 수: {len(merged_df.columns)}")

        # 메타데이터 보존
        merged_df.attrs = prev_table_df.attrs.copy()

        logger.debug(f"테이블 병합 완료: 이전 {len(prev_table_df)}행 + 현재 {len(current_df_to_merge)}행 = 총 {len(merged_df)}행")
        return merged_df

    except Exception as e:
        logger.error(f"테이블 병합 중 오류: {str(e)}")
        return prev_table_df


def reconstruct_text_with_merged_tables(original_text: str, merged_tables: list) -> str:
    """
    원본 텍스트에서 개별 테이블들을 병합된 테이블로 교체하되, 완벽한 원본 문서 구조를 유지합니다.

    테이블 병합으로 인한 인덱스 변화를 정확히 매핑하여 올바른 위치에 테이블을 배치합니다.

    Args:
        original_text: 페이지별로 추출된 원본 텍스트
        merged_tables: 병합된 테이블 정보 리스트

    Returns:
        str: 병합된 테이블로 재구성된 텍스트 (완벽한 원본 구조 유지)
    """
    if not merged_tables:
        return original_text

    # 1. 원본 텍스트에서 테이블들의 위치와 순서를 파악
    lines = original_text.split("\n")
    table_positions = []  # [(start_idx, end_idx, original_table_order), ...]
    current_table_start = None
    original_table_order = 0

    for i, line in enumerate(lines):
        is_table_line = line.strip().startswith("|") and "|" in line.strip()[1:]

        if is_table_line and current_table_start is None:
            # 테이블 시작
            current_table_start = i
        elif not is_table_line and current_table_start is not None:
            # 테이블 끝
            table_positions.append((current_table_start, i - 1, original_table_order))
            current_table_start = None
            original_table_order += 1

    # 마지막 테이블이 텍스트 끝까지 이어지는 경우
    if current_table_start is not None:
        table_positions.append((current_table_start, len(lines) - 1, original_table_order))

    logger.debug(f"원본 테이블 위치: {len(table_positions)}개, 병합된 테이블: {len(merged_tables)}개")

    # 2. 원본 테이블 → 병합된 테이블 매핑 테이블 구축
    original_to_merged_mapping = {}  # {원본_테이블_순서: 병합된_테이블_인덱스}

    # 병합된 테이블들을 페이지 순서로 정렬
    sorted_merged_tables = sorted(merged_tables, key=lambda x: (min(x.get("merged_from_pages", [x.get("page_num", 999)])), x.get("table_id", 0)))

    # 매핑 구축: 각 병합된 테이블이 원본의 몇 번째 테이블들을 대체하는지 추적
    current_original_index = 0

    for merged_idx, merged_table in enumerate(sorted_merged_tables):
        table_count_in_group = merged_table.get("table_count_in_group", 1)

        # 이 병합된 테이블이 대체하는 원본 테이블들의 범위
        for i in range(table_count_in_group):
            if current_original_index < len(table_positions):
                original_to_merged_mapping[current_original_index] = merged_idx
                logger.debug(f"매핑: 원본 테이블 {current_original_index} → 병합된 테이블 {merged_idx}")
                current_original_index += 1

    logger.debug(f"매핑 완료: {original_to_merged_mapping}")

    # 3. 원본 텍스트를 재구성 (뒤에서부터 교체해야 인덱스가 안 깨짐)
    result_lines = lines[:]
    processed_merged_tables = set()  # 이미 처리된 병합된 테이블 추적

    # 테이블 위치를 뒤에서부터 처리 (인덱스 변화 방지)
    for start_idx, end_idx, original_table_order in reversed(table_positions):
        if original_table_order in original_to_merged_mapping:
            merged_table_idx = original_to_merged_mapping[original_table_order]

            # 이미 처리된 병합된 테이블인 경우 해당 영역을 제거만 함
            if merged_table_idx in processed_merged_tables:
                logger.debug(f"원본 테이블 {original_table_order} 영역 제거 (이미 병합됨)")
                # 해당 테이블 영역을 빈 공간으로 대체
                result_lines[start_idx : end_idx + 1] = []
                continue

            # 처음 만나는 병합된 테이블인 경우 실제 테이블로 교체
            table_info = sorted_merged_tables[merged_table_idx]
            processed_merged_tables.add(merged_table_idx)

            if table_info.get("markdown"):
                # 병합 정보 표시
                pages_info = table_info.get("merged_from_pages", [table_info.get("page_num")])
                table_count_merge = table_info.get("table_count_in_group", 1)

                replacement_lines = []
                # if table_count_merge > 1:
                #     replacement_lines.append(f"### 📋 병합된 테이블 (페이지 {pages_info}에서 {table_count_merge}개 병합)")

                # 병합된 테이블의 마크다운 추가
                markdown_lines = table_info["markdown"].strip().split("\n")
                replacement_lines.extend(markdown_lines)

                # 원본 테이블 영역을 병합된 테이블로 교체
                result_lines[start_idx : end_idx + 1] = replacement_lines

                logger.debug(f"원본 테이블 {original_table_order} → 병합된 테이블 {merged_table_idx} 교체 완료")
        else:
            logger.debug(f"원본 테이블 {original_table_order}에 대응하는 병합된 테이블 없음 - 영역 제거")
            # 매핑되지 않은 원본 테이블 영역 제거 (병합되어 사라진 테이블)
            result_lines[start_idx : end_idx + 1] = []

    return "\n".join(result_lines)


def analyze_table_structure_across_pages(all_page_tables: list) -> list:
    """
    여러 페이지의 테이블들을 분석하여 연결된 테이블들을 그룹화합니다.

    Args:
        all_page_tables: 모든 페이지의 테이블 정보 리스트
                        [{'page_num': int, 'tables': [table_info, ...]}, ...]

    Returns:
        list: 그룹화된 테이블 리스트
              [{'tables': [merged_table_info], 'pages': [page_nums]}, ...]
    """
    if not all_page_tables:
        return []

    grouped_tables = []
    current_group = None

    for page_info in all_page_tables:
        page_num = page_info["page_num"]
        page_tables = page_info["tables"]

        for i, table_info in enumerate(page_tables):
            table_df = table_info.get("dataframe")

            if table_df is None or table_df.empty:
                continue

            # 첫 번째 테이블이거나 이전 그룹이 없으면 새 그룹 시작
            if current_group is None:
                current_group = {"merged_table": table_info, "pages": [page_num], "table_count": 1}
                continue

            # 1차: 좌표 기반 연속성 판단 (우선순위)
            prev_table_info = current_group["merged_table"]
            should_merge = False
            merge_reason = ""

            if is_position_based_continuation(prev_table_info, table_info):
                should_merge = True
                merge_reason = "좌표 기반 연속성"
                logger.debug(f"테이블 연결 판단: {merge_reason} 감지")
            else:
                # 2차: 기존 데이터 기반 연속성 판단 (보조)
                prev_table_df = current_group["merged_table"].get("dataframe")
                if is_table_continuation(prev_table_df, table_df):
                    should_merge = True
                    merge_reason = "데이터 기반 연속성"
                    logger.debug(f"테이블 연결 판단: {merge_reason} 감지")

            if should_merge:
                # 테이블 병합
                prev_table_df = current_group["merged_table"].get("dataframe")
                merged_df = merge_continued_tables(prev_table_df, table_df)

                # 그룹 정보 업데이트
                current_group["merged_table"]["dataframe"] = merged_df
                current_group["merged_table"]["original_dataframe"] = merged_df  # 원본도 업데이트
                current_group["pages"].append(page_num)
                current_group["table_count"] += 1

                # 마크다운도 다시 생성
                current_group["merged_table"]["markdown"] = dataframe_to_markdown(merged_df, current_group["merged_table"]["table_id"])

                logger.debug(f"✅ 테이블 병합 성공: 페이지 {page_num} 테이블 {i + 1} ({merge_reason}, 총 {len(merged_df)}행)")

            else:
                # 이전 그룹을 완료하고 새 그룹 시작
                grouped_tables.append(current_group)
                current_group = {"merged_table": table_info, "pages": [page_num], "table_count": 1}
                logger.debug(f"새로운 테이블 그룹 시작: 페이지 {page_num} 테이블 {i + 1}")

    # 마지막 그룹 추가
    if current_group is not None:
        grouped_tables.append(current_group)

    logger.info(f"테이블 그룹화 완료: 총 {len(grouped_tables)}개 그룹, 페이지 범위: {all_page_tables[0]['page_num']}~{all_page_tables[-1]['page_num']}")

    # 결과 포맷팅
    result = []
    for i, group in enumerate(grouped_tables):
        group_info = group["merged_table"].copy()
        group_info["merged_from_pages"] = group["pages"]
        group_info["table_count_in_group"] = group["table_count"]
        group_info["table_id"] = i + 1  # 새로운 테이블 ID 할당
        result.append(group_info)

    return result


async def extract_page_gemini_style_with_dataframe(page, page_num: int):
    """
    Gemini 방식으로 단일 페이지에서 테이블과 텍스트를 추출하고 DataFrame으로 변환합니다.

    Args:
        page: pdfplumber page 객체
        page_num: 페이지 번호

    Returns:
        dict: {
            'text': str,  # 추출된 텍스트
            'tables': [   # 추출된 테이블 리스트
                {
                    'table_id': int,
                    'page_num': int,
                    'dataframe': pd.DataFrame,
                    'unit_info': str,
                    'markdown': str,
                    'raw_data': list
                }
            ]
        }
    """
    try:
        result = {"text": "", "tables": []}

        page_content = ""

        # 1. 페이지에 있는 테이블들의 위치 정보 찾기
        tables = page.find_tables()

        if not tables:
            # 테이블이 없으면 전체를 텍스트로 추출
            text = page.extract_text()
            if text:
                page_content += text
            result["text"] = page_content
            return result

        logger.debug(f"페이지 {page_num}에서 {len(tables)} 개의 테이블을 발견했습니다 (DataFrame 방식).")

        # 2. 테이블들을 Y 좌표 기준으로 정렬
        sorted_tables = sorted(tables, key=lambda t: t.bbox[1])  # Y 좌표(상단) 기준 정렬

        current_y = 0  # 페이지 상단부터 시작

        for i, table in enumerate(sorted_tables):
            table_bbox = table.bbox  # (x0, top, x1, bottom)

            # 3. 테이블 '위쪽' 영역을 잘라내서 텍스트 추출 (단위 정보 포함)
            unit_info = ""
            text_above_table_content = ""  # 텍스트 내용을 임시 저장할 변수
            if table_bbox[1] > current_y:  # 테이블 상단이 현재 Y 위치보다 아래에 있으면
                try:
                    top_part_bbox = (0, current_y, page.width, table_bbox[1])
                    text_above_table = page.crop(top_part_bbox).extract_text()
                    if text_above_table and text_above_table.strip():
                        text_above_table_content = text_above_table.strip()  # 임시 변수에 저장
                        # 단위 정보 추출
                        unit_info = extract_unit_info(text_above_table_content)
                except Exception as crop_error:
                    logger.debug(f"테이블 {i + 1} 위쪽 텍스트 추출 오류: {str(crop_error)}")

            # 4. 테이블 영역을 잘라내서 구조화된 데이터로 추출
            try:
                # Gemini 방식의 핵심: 명시적인 테이블 추출 전략 사용
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "edge_min_length": 3,
                    "min_words_vertical": 1,
                    "min_words_horizontal": 1,
                }

                structured_table = page.crop(table_bbox).extract_table(table_settings)

                if structured_table and len(structured_table) > 0:
                    # 단위 정보가 테이블 위에서 찾아지지 않았을 경우, 테이블 내부에서 다시 검색
                    if not unit_info:
                        # 테이블의 첫번째 행을 순회하며 단위 정보 탐색
                        for cell_content in structured_table[0]:
                            if cell_content:
                                new_unit_info = extract_unit_info(str(cell_content))
                                if new_unit_info:
                                    unit_info = new_unit_info
                                    logger.debug(f"테이블 {i + 1} 내부에서 단위 정보 발견: '{unit_info}'. 해당 행을 테이블에서 제거합니다.")
                                    # 단위 정보를 포함한 행은 실제 데이터가 아니므로 제거
                                    structured_table = structured_table[1:]
                                    break  # 단위 정보를 찾았으면 반복 중단

                    # DataFrame 생성
                    df = create_dataframe_from_table(structured_table, unit_info)

                    # 단위 변환 수행 (단위 정보가 있는 경우)
                    converted_df = df
                    target_unit = "십억원"  # 기본 타겟 단위

                    # 소스 단위에 따라 적절한 타겟 단위 선택
                    if unit_info:
                        source_unit_clean = unit_info.replace("단위:", "").replace("단위 :", "").strip().lower()
                        if "백만원" in source_unit_clean:
                            target_unit = "십억원"  # 백만원 -> 십억원
                        elif "천원" in source_unit_clean:
                            target_unit = "억원"  # 천원 -> 억원
                        elif "원" in source_unit_clean and "억" not in source_unit_clean:
                            target_unit = "백만원"  # 원 -> 백만원
                        elif "억원" in source_unit_clean:
                            target_unit = "조원"  # 억원 -> 조원
                        else:
                            target_unit = "십억원"  # 기본값

                        # 원본 텍스트의 단위 정보 교체
                        source_unit_name = source_unit_clean.split(",")[0].strip()
                        if source_unit_name and text_above_table_content:
                            text_above_table_content = replace_unit_in_text(text_above_table_content, source_unit_name, target_unit)

                    if text_above_table_content:
                        page_content += f"{text_above_table_content}\n"

                    if unit_info and df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                        try:
                            # 단위 변환 실행
                            converted_df = convert_dataframe_units(df, unit_info, target_unit)

                            # 변환 결과 검증
                            if converted_df is not None and isinstance(converted_df, pd.DataFrame) and not converted_df.empty:
                                logger.debug(f"테이블 {i + 1} 단위 변환 완료: {unit_info} -> {target_unit}")
                                logger.debug(f"테이블 {i + 1} 변환 검증: 변환된 DataFrame 크기 {converted_df.shape}")
                            else:
                                logger.debug(f"테이블 {i + 1} 변환 실패: 빈 DataFrame 반환됨")
                                converted_df = df

                        except Exception as convert_error:
                            logger.debug(f"테이블 {i + 1} 단위 변환 오류: {str(convert_error)}")
                            # 변환 중 오류가 발생했지만 이미 변환된 DataFrame이 있으면 그것을 사용
                            if converted_df is not None and isinstance(converted_df, pd.DataFrame) and not converted_df.empty:
                                logger.debug(f"테이블 {i + 1} 오류에도 불구하고 변환된 DataFrame 유지: {converted_df.shape}")
                            else:
                                converted_df = df  # 완전 실패 시에만 원본 사용

                    # DataFrame을 마크다운으로 변환
                    if converted_df is not None and not converted_df.empty:
                        markdown_content = dataframe_to_markdown(converted_df, i + 1)
                    else:
                        # DataFrame이 비어있으면 원본 방식으로 폴백
                        markdown_content = ""
                        for row_idx, row in enumerate(structured_table):
                            if row and any(cell for cell in row if cell):
                                cleaned_row = []
                                for cell in row:
                                    if cell:
                                        clean_cell = str(cell).strip().replace("\n", " ").replace("\r", "")
                                        clean_cell = " ".join(clean_cell.split())
                                        cleaned_row.append(clean_cell)
                                    else:
                                        cleaned_row.append("")

                                markdown_content += "| " + " | ".join(cleaned_row) + " |\n"

                                # 헤더 행 다음에 구분선 추가
                                if row_idx == 0 and len(structured_table) > 1:
                                    separator = ["---"] * len(cleaned_row)
                                    markdown_content += "| " + " | ".join(separator) + " |\n"
                        markdown_content += "\n"

                    page_content += markdown_content

                    # 테이블 정보 저장
                    final_df = converted_df if converted_df is not None else df
                    table_info = {
                        "table_id": i + 1,
                        "page_num": page_num,
                        "dataframe": final_df,  # 변환된 DataFrame 우선 저장
                        "original_dataframe": df,  # 원본 DataFrame도 저장
                        "unit_info": unit_info,
                        "converted_unit": f"단위: {target_unit}" if unit_info else "",
                        "markdown": markdown_content,
                        "raw_data": structured_table,
                        "bbox": table_bbox,  # 좌표 정보 추가
                        "table_position_in_page": i,  # 페이지 내 테이블 순서
                    }

                    # 저장된 DataFrame 검증
                    logger.debug(f"테이블 {i + 1} 저장 검증: final_df 크기 {final_df.shape if final_df is not None else 'None'}")
                    if final_df is not None and not final_df.empty and len(final_df) > 0:
                        sample_cell = final_df.iloc[0, 0] if len(final_df.columns) > 0 else "N/A"
                        logger.debug(f"테이블 {i + 1} 저장된 샘플 값: [0,0] = '{sample_cell}'")
                    result["tables"].append(table_info)

                    logger.debug(
                        f"테이블 {i + 1} DataFrame 처리 완료: {converted_df.shape if converted_df is not None else 'None'}, 단위: {unit_info} -> {target_unit if unit_info else '변환안함'}"
                    )
                else:
                    raise Exception("구조화된 테이블 추출 실패")

            except Exception as table_error:
                logger.debug(f"테이블 {i + 1} 구조화 추출 오류 (DataFrame 방식): {str(table_error)}")
                # 폴백: 테이블 영역을 텍스트로 추출
                try:
                    table_text = page.crop(table_bbox).extract_text()
                    if table_text and table_text.strip():
                        page_content += f"[테이블 {i + 1} - 텍스트 형태]\n{table_text.strip()}\n\n"
                        logger.debug(f"테이블 {i + 1} 텍스트 추출 성공 (폴백): {len(table_text)} 글자")
                except Exception as fallback_error:
                    logger.error(f"테이블 {i + 1} 모든 추출 방법 실패: {str(fallback_error)}")

            # 현재 Y 위치를 테이블 하단으로 업데이트
            current_y = table_bbox[3]

        # 5. 마지막 테이블 '아래쪽' 영역을 잘라내서 텍스트 추출
        if current_y < page.height:
            try:
                bottom_part_bbox = (0, current_y, page.width, page.height)
                text_below_table = page.crop(bottom_part_bbox).extract_text()
                if text_below_table and text_below_table.strip():
                    page_content += f"{text_below_table.strip()}\n"
            except Exception as crop_error:
                logger.debug(f"마지막 테이블 아래쪽 텍스트 추출 오류: {str(crop_error)}")

        cleaned_page_content = _clean_extracted_text(page_content)
        result["text"] = cleaned_page_content
        return result

    except Exception as e:
        logger.error(f"페이지 {page_num} DataFrame 방식 추출 중 오류: {str(e)}")
        # 오류가 발생하면 일반 텍스트 추출로 폴백
        try:
            fallback_text = page.extract_text()
            cleaned_fallback_text = _clean_extracted_text(fallback_text)
            return {"text": f"[폴백 텍스트]\n{cleaned_fallback_text}\n" if cleaned_fallback_text else "", "tables": []}
        except Exception as fallback_error:
            logger.error(f"페이지 {page_num} 폴백 텍스트 추출 오류: {str(fallback_error)}")
            return {"text": "", "tables": []}


async def extract_page_gemini_style(page, page_num: int):
    """
    Gemini 방식으로 단일 페이지에서 테이블과 텍스트를 추출합니다.

    핵심 차이점:
    1. page.crop(bbox).extract_table(settings) 사용
    2. 명시적인 테이블 추출 전략 적용
    3. 정교한 영역 분할

    Args:
        page: pdfplumber page 객체
        page_num: 페이지 번호

    Returns:
        str: 추출된 텍스트 (테이블 + 주변 텍스트)
    """
    try:
        page_content = ""

        # 1. 페이지에 있는 테이블들의 위치 정보 찾기
        tables = page.find_tables()

        if not tables:
            # 테이블이 없으면 전체를 텍스트로 추출
            text = page.extract_text()
            if text:
                page_content += text
            return page_content

        logger.debug(f"페이지 {page_num}에서 {len(tables)} 개의 테이블을 발견했습니다 (Gemini 방식).")

        # 2. 테이블들을 Y 좌표 기준으로 정렬
        sorted_tables = sorted(tables, key=lambda t: t.bbox[1])  # Y 좌표(상단) 기준 정렬

        current_y = 0  # 페이지 상단부터 시작

        for i, table in enumerate(sorted_tables):
            table_bbox = table.bbox  # (x0, top, x1, bottom)

            # 3. 테이블 '위쪽' 영역을 잘라내서 텍스트 추출
            if table_bbox[1] > current_y:  # 테이블 상단이 현재 Y 위치보다 아래에 있으면
                try:
                    top_part_bbox = (0, current_y, page.width, table_bbox[1])
                    text_above_table = page.crop(top_part_bbox).extract_text()
                    if text_above_table and text_above_table.strip():
                        page_content += f"{text_above_table.strip()}\n"
                except Exception as crop_error:
                    logger.debug(f"테이블 {i + 1} 위쪽 텍스트 추출 오류: {str(crop_error)}")

            # 4. 테이블 영역을 잘라내서 구조화된 데이터로 추출
            try:
                # Gemini 방식의 핵심: 명시적인 테이블 추출 전략 사용
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    # 추가 정교한 설정
                    "snap_tolerance": 3,  # 라인 스냅 허용 오차
                    "join_tolerance": 3,  # 라인 결합 허용 오차
                    "edge_min_length": 3,  # 최소 엣지 길이
                    "min_words_vertical": 1,  # 세로 구분 최소 단어 수
                    "min_words_horizontal": 1,  # 가로 구분 최소 단어 수
                }

                structured_table = page.crop(table_bbox).extract_table(table_settings)

                if structured_table and len(structured_table) > 0:
                    # page_content += f"[테이블 {i + 1}]\n"

                    # 구조화된 테이블을 마크다운 테이블 형태로 변환
                    for row_idx, row in enumerate(structured_table):
                        if row and any(cell for cell in row if cell):  # 빈 행이 아닌 경우만
                            # None 값을 빈 문자열로 변환하고 각 셀 정리
                            cleaned_row = []
                            for cell in row:
                                if cell:
                                    # 셀 내용 정리: 불필요한 공백 제거, 줄바꿈을 공백으로 변환
                                    clean_cell = str(cell).strip().replace("\n", " ").replace("\r", "")
                                    # 연속된 공백을 하나로 통합
                                    clean_cell = " ".join(clean_cell.split())
                                    cleaned_row.append(clean_cell)
                                else:
                                    cleaned_row.append("")

                            page_content += "| " + " | ".join(cleaned_row) + " |\n"

                            # 헤더 행 다음에 구분선 추가
                            if row_idx == 0 and len(structured_table) > 1:
                                separator = ["---"] * len(cleaned_row)
                                page_content += "| " + " | ".join(separator) + " |\n"

                    page_content += "\n"
                    logger.debug(f"테이블 {i + 1} 구조화 추출 성공 (Gemini 방식): {len(structured_table)} 행")
                else:
                    raise Exception("구조화된 테이블 추출 실패")

            except Exception as table_error:
                logger.debug(f"테이블 {i + 1} 구조화 추출 오류 (Gemini 방식): {str(table_error)}")
                # 폴백: 테이블 영역을 텍스트로 추출
                try:
                    table_text = page.crop(table_bbox).extract_text()
                    if table_text and table_text.strip():
                        page_content += f"[테이블 {i + 1} - 텍스트 형태]\n{table_text.strip()}\n\n"
                        logger.debug(f"테이블 {i + 1} 텍스트 추출 성공 (폴백): {len(table_text)} 글자")
                except Exception as fallback_error:
                    logger.error(f"테이블 {i + 1} 모든 추출 방법 실패: {str(fallback_error)}")

            # 현재 Y 위치를 테이블 하단으로 업데이트
            current_y = table_bbox[3]

        # 5. 마지막 테이블 '아래쪽' 영역을 잘라내서 텍스트 추출
        if current_y < page.height:
            try:
                bottom_part_bbox = (0, current_y, page.width, page.height)
                text_below_table = page.crop(bottom_part_bbox).extract_text()
                if text_below_table and text_below_table.strip():
                    page_content += f"{text_below_table.strip()}\n"
            except Exception as crop_error:
                logger.debug(f"마지막 테이블 아래쪽 텍스트 추출 오류: {str(crop_error)}")

        cleaned_page_content = _clean_extracted_text(page_content)
        return cleaned_page_content

    except Exception as e:
        logger.error(f"페이지 {page_num} Gemini 방식 추출 중 오류: {str(e)}")
        # 오류가 발생하면 일반 텍스트 추출로 폴백
        try:
            fallback_text = page.extract_text()
            if fallback_text:
                return f"[폴백 텍스트]\n{fallback_text}\n"
        except Exception as fallback_error:
            logger.error(f"페이지 {page_num} 폴백 텍스트 추출 오류: {str(fallback_error)}")
        return ""


def test_unit_conversion():
    """
    단위 변환 함수들을 테스트합니다.
    """
    print("=== 단위 변환 테스트 ===")

    # 1. parse_unit_to_multiplier 테스트
    print("\n1. parse_unit_to_multiplier 테스트:")
    test_units = ["백만원", "십억원", "원", "억원", "조원"]
    for unit in test_units:
        multiplier = parse_unit_to_multiplier(unit)
        print(f"  {unit}: {multiplier:,}")

    # 2. is_numeric_value 테스트
    print("\n2. is_numeric_value 테스트:")
    test_values = ["11,267", "4.59%", "-", "68,070", "0.00%", "29,761"]
    for value in test_values:
        is_numeric = is_numeric_value(value)
        print(f"  '{value}': {is_numeric}")

    # 3. convert_value_to_target_unit 테스트
    print("\n3. convert_value_to_target_unit 테스트:")
    source_multiplier = 1000000  # 백만원
    target_multiplier = 1000000000  # 십억원
    test_conversions = ["11,267", "68,070", "33,927"]

    for value in test_conversions:
        converted = convert_value_to_target_unit(value, source_multiplier, target_multiplier)
        print(f"  '{value}' 백만원 -> '{converted}' 십억원")

    print("\n=== 단위 변환 테스트 완료 ===\n")


async def test_all():
    start_time = time.time()

    ff = "stockeasy/local_cache/financial_reports/정기보고서/089030/20250301_테크윙_089030_기계·장비_Q1_DART.pdf"
    ff = "stockeasy/local_cache/financial_reports/정기보고서/007660/20240901_이수페타시스_007660_전기·전자_Q3_DART.pdf"
    # ff = "stockeasy/local_cache/financial_reports/정기보고서/257720/20250301_실리콘투_257720_유통_Q1_DART.pdf"
    # ff = "stockeasy/local_cache/financial_reports/정기보고서/083650/20250301_비에이치아이_083650_기계·장비_Q1_DART.pdf"
    ff = "stockeasy/local_cache/financial_reports/정기보고서/112610/20240901_씨에스윈드_112610_금속_Q3_DART.pdf"
    ff = "stockeasy/local_cache/financial_reports/정기보고서/000660/20250301_SK하이닉스_000660_전기·전자_Q1_DART.pdf"
    ff = "stockeasy/local_cache/financial_reports/정기보고서/000660/20250301_HD현대일렉트릭_267260_전기·전자_Q1_DART.pdf"
    print("=== PDF 테스트 (간소화) ===")
    result_gemini = await extract_revenue_breakdown_data_3(ff)

    if result_gemini == "":
        print("파일이 없어욧.")
        return
    elif isinstance(result_gemini, dict):
        print("\n\n--- PDF 추출 결과 ---")
        print(result_gemini.get("text", "추출된 텍스트가 없습니다."))
        print("--- PDF 추출 결과 끝 ---\n\n")

        tables = result_gemini.get("tables", [])
        if tables:
            print("\n=== 테이블 병합 결과 분석 ===")
            print(f"총 테이블 개수: {len(tables)}")

            # 병합 성공한 테이블 개수 확인
            merged_count = sum(1 for table in tables if table.get("table_count_in_group", 1) > 1)
            print(f"병합 성공한 테이블: {merged_count}개")

            # 모든 테이블의 병합 정보 출력
            for i, table in enumerate(tables):
                merged_pages = table.get("merged_from_pages", [table.get("page_num", "?")])
                table_count = table.get("table_count_in_group", 1)
                df = table.get("dataframe")
                df_shape = df.shape if df is not None else (0, 0)

                print(f"\n테이블 {i + 1}:")
                print(f"  - 병합된 페이지: {merged_pages}")
                print(f"  - 병합된 테이블 개수: {table_count}")
                print(f"  - DataFrame 크기: {df_shape}")
                print(f"  - 단위 정보: {table.get('unit_info', '없음')}")
                print(f"  - 변환 단위: {table.get('converted_unit', '없음')}")

                # 컬럼 정보도 출력
                if df is not None and not df.empty:
                    columns_preview = list(df.columns)[:5]  # 처음 5개 컬럼만
                    if len(df.columns) > 5:
                        columns_preview.append("...")
                    print(f"  - 컬럼: {columns_preview}")

                # 병합된 테이블이 있으면 더 자세히 표시
                if table_count > 1:
                    print("  ✅ 페이지 간 병합 성공!")

                    # bbox 정보 확인
                    bbox_info = table.get("bbox")
                    if bbox_info:
                        print(f"    좌표 정보: {bbox_info}")
                    else:
                        print("    ⚠️  좌표 정보 없음")

            # 특별 케이스: 테이블 2와 3 병합 상황 확인
            table_2_3_merged = False
            for table in tables:
                merged_pages = table.get("merged_from_pages", [])
                if len(merged_pages) >= 2 and 17 in merged_pages and 18 in merged_pages:
                    table_2_3_merged = True
                    print(f"  🎯 테이블 2와 3 병합 성공! 페이지: {merged_pages}")
                    break

            if not table_2_3_merged:
                print("  ❌ 테이블 2와 3이 병합되지 않았습니다.")
                # 개별 테이블들의 상세 정보 출력
                for i, table in enumerate(tables):
                    pages = table.get("merged_from_pages", [table.get("page_num")])
                    df = table.get("dataframe")
                    if df is not None and not df.empty and len(pages) == 1:
                        print(f"    테이블 {i + 1} (페이지 {pages[0]}): {df.shape}")
                        if len(df.columns) <= 6:  # 컬럼이 적으면 출력
                            print(f"      컬럼: {list(df.columns)}")
                        if len(df) <= 5:  # 행이 적으면 샘플 출력
                            print(f"      샘플 데이터:\n{df.head(3).to_string(index=False)}")

            # 가장 큰 테이블이나 병합된 테이블 찾기
            target_table = None
            for table in tables:
                df = table.get("dataframe")
                if df is not None and not df.empty:
                    # 병합된 테이블을 우선으로 선택
                    if table.get("table_count_in_group", 1) > 1:
                        target_table = table
                        break
                    # 아니면 가장 큰 테이블 선택
                    elif target_table is None or len(df) > len(target_table.get("dataframe", pd.DataFrame())):
                        target_table = table

            # if target_table:
            #     print("\n=== 대상 테이블 상세 분석 ===")
            #     merged_pages = target_table.get("merged_from_pages", [target_table.get("page_num", "?")])
            #     table_count = target_table.get("table_count_in_group", 1)

            #     print(f"선택된 테이블: 페이지 {merged_pages}, {table_count}개 병합")
            #     print(f"원본 단위: {target_table.get('unit_info', '없음')}")
            #     print(f"변환 단위: {target_table.get('converted_unit', '없음')}")

            #     # 원본과 변환된 DataFrame 비교
            #     original_df = target_table.get("original_dataframe")
            #     converted_df = target_table.get("dataframe")

            #     if original_df is not None and not original_df.empty:
            #         print(f"\n[원본 DataFrame 샘플] - 크기: {original_df.shape}")
            #         print(original_df.head(10).to_string(index=False))

            #     if converted_df is not None and not converted_df.empty:
            #         print(f"\n[변환된 DataFrame 샘플] - 크기: {converted_df.shape}")
            #         print(converted_df.head(10).to_string(index=False))

            #         # 병합된 경우 중간 부분도 확인
            #         if len(converted_df) > 15:
            #             print("\n[변환된 DataFrame 중간 부분]")
            #             mid_start = len(converted_df) // 2 - 2
            #             mid_end = len(converted_df) // 2 + 3
            #             print(converted_df.iloc[mid_start:mid_end].to_string(index=False))

            # else:
            #     print("\n❌ 분석할 테이블을 찾을 수 없습니다.")
    else:
        print("결과가 딕셔너리 형태가 아닙니다.")
        result_gemini = None

    end_time = time.time()
    print(f"\n⏱️ 총 실행 시간: {end_time - start_time:.2f}초")
    return result_gemini


if __name__ == "__main__":
    asyncio.run(test_all())
