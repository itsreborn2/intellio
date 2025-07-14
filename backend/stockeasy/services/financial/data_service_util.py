import logging
import re  # 정규식 라이브러리
import warnings

import fitz  # PyMuPDF 라이브러리
import pandas as pd  # DataFrame 라이브러리
from dotenv import load_dotenv

# markdown을 html로 변환하는 라이브러리 추가
# LangChain 관련 라이브러리
# OpenAI 모델 임포트 추가
# from langchain_openai import ChatOpenAI
from loguru import logger

warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
warnings.filterwarnings("ignore", category=UserWarning, module="pdfplumber")
warnings.filterwarnings("ignore", category=UserWarning, module="fitz")  # PyMuPDF 경고 숨기기
warnings.filterwarnings("ignore", message="CropBox missing from /Page, defaulting to MediaBox")

# fitz 라이브러리의 경고 출력 레벨 변경 (0: 모든 출력, 1: 경고만, 2: 오류만, 3: 모두 억제)
# 모든 경고 메시지 억제
fitz.TOOLS.mupdf_warnings_handler = lambda warn_level, message: None
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

    # 전각/반각 문자 정규화 및 특수 공백 처리
    normalized_text = text.replace("\u3000", " ")  # 전각 스페이스
    normalized_text = normalized_text.replace("\xa0", " ")  # NBSP
    normalized_text = normalized_text.replace("（", "(").replace("）", ")")  # 전각 괄호
    normalized_text = normalized_text.replace("：", ":")  # 전각 콜론
    normalized_text = normalized_text.replace("［", "[").replace("］", "]")  # 전각 대괄호
    normalized_text = " ".join(normalized_text.split())  # 연속 공백 정리

    # 단위 정보를 찾는 정규식 패턴들 (개선된 버전)
    unit_patterns = [
        # 괄호 패턴: (단위: 원), (단위 : 십억원, USD), (단위 : 백만USD)
        r"\(\s*단위\s*[:\s]\s*([^)]+)\)",
        # 대괄호 패턴: [단위: 원], [단위 : 백만USD]
        r"\[\s*단위\s*[:\s]\s*([^\]]+)\]",
        # 화살괄호 패턴: <단위: 원>
        r"<\s*단위\s*[:\s]\s*([^>]+)>",
        # 일반 패턴: 단위: 원, 단위 : 십억원 (줄바꿈이나 쉼표 전까지)
        r"단위\s*[:\s]\s*([^,\n\r\t]+)",
    ]

    # logger.debug(f"단위 정보 추출 시도: 원본텍스트='{text[:100]}...' 정규화텍스트='{normalized_text[:100]}...'")

    for i, pattern in enumerate(unit_patterns):
        try:
            matches = re.findall(pattern, normalized_text, re.IGNORECASE)
            if matches:
                # 가장 첫 번째 매치 반환, 앞뒤 공백 제거
                unit = matches[0].strip()
                # logger.debug(f"단위 정보 추출 성공: 패턴{i + 1} '{pattern}' -> '{unit}'")
                return f"단위: {unit}"
            # else:
            #     logger.debug(f"단위 정보 패턴{i + 1} 매칭 실패: '{pattern}'")
        except Exception as e:
            logger.debug(f"단위 정보 패턴{i + 1} 처리 오류: {str(e)}")

    # logger.debug("단위 정보 추출 실패: 모든 패턴에서 매칭되지 않음")
    return ""


def get_max_abs_value_from_dataframe(df: pd.DataFrame) -> float:
    """
    DataFrame에서 숫자 값 중 최대 절댓값을 구합니다.

    Args:
        df: 분석할 DataFrame

    Returns:
        float: 최대 절댓값
    """
    max_abs_val = 0
    for col in df.columns:
        for idx in df.index:
            val_str = str(df.at[idx, col])
            if is_numeric_value(val_str):
                try:
                    clean_val = val_str.replace(",", "").replace("(", "").replace(")", "")
                    if clean_val.startswith("-"):
                        clean_val = clean_val[1:]
                    num_val = float(clean_val)
                    if abs(num_val) > max_abs_val:
                        max_abs_val = abs(num_val)
                except Exception:
                    pass
    return max_abs_val


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


def remove_unit_from_text(text: str) -> str:
    """
    텍스트에서 단위 정보 문자열을 제거합니다.
    예: (단위: 백만원) -> ""

    Args:
        text: 원본 텍스트

    Returns:
        str: 단위 정보가 제거된 텍스트
    """
    if not text:
        return ""

    unit_patterns = [
        r"\s*\(단위[:\s]*[^)]+\)",  # (단위: 원)
        r"\s*단위[:\s]*[^,\n\r]+",  # 단위: 원
        r"\s*\[단위[:\s]*[^\]]+\]",  # [단위: 원]
        r"\s*<단위[:\s]*[^>]+>",  # <단위: 원>
    ]

    for pattern in unit_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


def replace_unit_in_text(original_text: str, old_unit_name: str, new_unit_name: str) -> str:
    """
    텍스트 내에서 '단위:'와 같은 키워드가 포함된 줄의 단위만 정확하게 교체합니다.
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

    import re

    lines = original_text.split("\n")
    new_lines = []

    for line in lines:
        # '단위' 키워드가 있는 줄에서만 교체를 시도
        if "단위" in line:
            # 단위 패턴을 정확하게 매칭하여 교체: 공백 허용 패턴
            # ( 단위 : 백만원), (단위: 백만원), ( 단위: 백만원) 등 모든 형태 지원
            unit_patterns = [
                # 기본 패턴: ( 단위 : 백만원) - ( 뒤와 단위 뒤 모두 공백 허용
                r"(\(\s*단위\s*:\s*)" + re.escape(old_unit_name) + r"(\s*\))",
                # 복합 패턴: ( 단위 : 백만원, USD) - 복합 단위도 공백 허용
                r"(\(\s*단위\s*:\s*)" + re.escape(old_unit_name) + r"(\s*,.*?\))",
                # 괄호 없는 패턴: 단위 : 백만원 - 괄호 없이도 공백 허용
                r"(단위\s*:\s*)" + re.escape(old_unit_name) + r"(\s*(?:[,\n]|$))",
            ]

            replaced = False
            for i, pattern in enumerate(unit_patterns):
                if re.search(pattern, line):
                    new_line = re.sub(pattern, r"\1" + new_unit_name + r"\2", line)
                    logger.debug(f"단위 교체 패턴 {i + 1} 매치: '{line.strip()}' → '{new_line.strip()}'")
                    new_lines.append(new_line)
                    replaced = True
                    break

            if not replaced:
                # 최후의 수단: 독립적인 단위만 교체 (접두사가 있는 경우 제외)
                # 예: "원"을 "백만원"으로 바꿀 때 "십억원"의 "원"은 교체하지 않음
                if old_unit_name in line and new_unit_name not in line:
                    # 독립적인 단위인지 확인 (앞에 다른 단위가 붙어있지 않은지)
                    import re

                    # 단위 앞에 다른 문자(한글/숫자)가 붙어있으면 교체하지 않음
                    independent_pattern = r"(?<![가-힣\d])" + re.escape(old_unit_name) + r"(?![가-힣\d])"
                    if re.search(independent_pattern, line):
                        logger.debug(f"단위 교체 fallback: '{line.strip()}' → '{re.sub(independent_pattern, new_unit_name, line).strip()}'")
                        new_lines.append(re.sub(independent_pattern, new_unit_name, line))
                    else:
                        logger.debug(f"단위 교체 건너뜀: '{line.strip()}' (독립적이지 않은 단위 - 접두사 존재)")
                        new_lines.append(line)
                else:
                    logger.debug(f"단위 교체 건너뜀: '{line.strip()}' (이미 {new_unit_name} 포함 또는 {old_unit_name} 없음)")
                    new_lines.append(line)
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

        # 단위 변환
        converted_value = numeric_value * source_multiplier / target_multiplier

        # 포맷팅
        if converted_value == 0:
            formatted = "0"
        elif abs(converted_value) >= 1000:  # 1000 이상이면, 반올림하여 정수로 표시
            formatted = f"{round(converted_value):,.0f}"
        elif abs(converted_value) >= 10:  # 10 이상이면, 소수점 1자리
            formatted = f"{converted_value:,.1f}".rstrip("0").rstrip(".")
        else:
            formatted = f"{converted_value:.2f}".rstrip("0").rstrip(".")
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
    source_unit_full = source_unit.replace("단위:", "").replace("단위 :", "").strip()
    source_unit_parts = [p.strip() for p in source_unit_full.split(",")]
    source_unit_clean = source_unit_parts[0]

    # 외화 단위 확인 (변환하지 않음)
    foreign_currencies = ["usd", "eur", "jpy", "cny", "gbp", "krw", "dollar", "euro", "yen", "yuan", "pound"]
    source_unit_lower = source_unit_clean.lower()

    # 외화 단위가 포함된 경우 변환하지 않고 원본 DataFrame 반환
    if any(currency in source_unit_lower for currency in foreign_currencies):
        # logger.debug(f"외화 단위 감지: '{source_unit_clean}' - 단위 변환을 건너뜁니다")
        # 원본 DataFrame을 복사하되 단위 정보만 메타데이터로 추가
        result_df = df.copy()
        result_df.attrs["original_unit"] = source_unit
        result_df.attrs["converted_unit"] = source_unit  # 변환하지 않았으므로 원본 단위 유지
        return result_df

    # 단위 배수 계산
    source_multiplier = parse_unit_to_multiplier(source_unit_clean)
    target_multiplier = parse_unit_to_multiplier(target_unit)

    # 변환할 수 없는 단위인 경우 (source_multiplier가 1.0인 경우)
    if source_multiplier == 1.0 and source_unit_clean.lower() not in ["원", "won"]:
        # logger.debug(f"알 수 없는 단위: '{source_unit_clean}' - 단위 변환을 건너뜁니다")
        result_df = df.copy()
        result_df.attrs["original_unit"] = source_unit
        result_df.attrs["converted_unit"] = source_unit
        return result_df

    # logger.debug(f"단위 변환: {source_unit_clean} ({source_multiplier:,}) -> {target_unit} ({target_multiplier:,})")

    # pandas DataFrame의 완전한 복사 (새로운 독립 객체 생성)
    converted_df = pd.DataFrame(df.values.copy(), columns=df.columns.copy(), index=df.index.copy())

    # logger.debug(f"변환 시작 - 원본 DataFrame 크기: {df.shape}")
    # logger.debug(f"변환용 DataFrame ID: {id(converted_df)}, 원본 DataFrame ID: {id(df)}")
    # logger.debug(f"DataFrame 독립성 확인: {id(converted_df) != id(df)}")

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

    # logger.debug(f"총 {conversion_count}개 셀이 변환되었습니다.")

    # 변환 완료 후 샘플 값 확인
    if conversion_count > 0:
        sample_row = 0
        for col in converted_df.columns:
            val = converted_df.at[sample_row, col] if sample_row < len(converted_df) else None
            if val and is_numeric_value(str(val)):
                # logger.debug(f"변환 완료 샘플 확인: [{sample_row}, '{col}'] = '{val}'")
                break

    # 메타데이터 업데이트
    new_unit_parts = [target_unit] + source_unit_parts[1:]
    new_unit_full = ", ".join(new_unit_parts)
    converted_df.attrs["original_unit"] = source_unit
    converted_df.attrs["converted_unit"] = f"단위: {new_unit_full}"

    # 최종 검증: 변환이 제대로 적용되었는지 확인
    # logger.debug("=== 변환 결과 최종 검증 ===")
    verification_count = 0
    for col in converted_df.columns:
        for idx in converted_df.index:
            current_value = converted_df.at[idx, col]
            if current_value and is_numeric_value(str(current_value)):
                original_in_df = df.at[idx, col] if idx in df.index and col in df.columns else None
                # logger.debug(f"검증: [{idx}, '{col}'] 원본='{original_in_df}' 현재='{current_value}'")
                verification_count += 1
                if verification_count >= 3:  # 처음 3개만 검증
                    break
        if verification_count >= 3:
            break
    # logger.debug("=== 검증 완료 ===")

    return converted_df


def dataframe_to_markdown(df: pd.DataFrame, table_id: int = 1, source: str = "") -> str:
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

    # 단위 정보가 있으면 추가 (변환된 단위 우선, 없으면 원본 단위)
    unit_to_display = df.attrs.get("converted_unit") or df.attrs.get("unit_info", "")
    if source == "최종데이터" and unit_to_display:
        markdown_content += f"({str(unit_to_display).strip()})\n"

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

                # 📋 개선: 데이터 행에서 헤더명(Unnamed 시리즈) 제거
                if clean_value.startswith("Unnamed"):
                    row_data.append("")
                else:
                    row_data.append(clean_value)

        # 빈 행이 아닌 경우만 추가
        if any(cell for cell in row_data if cell):
            markdown_content += "| " + " | ".join(row_data) + " |\n"

    markdown_content += "\n"
    return markdown_content


def create_dataframe_from_table(table_data: list, unit_info: str = "", has_header: bool = True):
    """
    테이블 데이터를 pandas DataFrame으로 변환합니다.

    ⚠️ 이 함수는 단순히 2차원 배열을 DataFrame으로 변환하는 역할만 합니다.
    헤더 판단은 상위 함수에서 컨텍스트 정보를 가지고 처리해야 합니다.

    Args:
        table_data: 2차원 리스트 형태의 테이블 데이터
        unit_info: 단위 정보
        has_header: 첫 번째 행이 헤더인지 여부 (상위 함수에서 결정)

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

        # 헤더 처리 (상위 함수에서 결정된 has_header 파라미터 기반)
        if has_header and len(cleaned_data) > 0:
            # 컬럼명 설정 및 중복 처리
            header = list(cleaned_data[0])
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

            if len(cleaned_data) == 1:
                # 헤더만 있는 테이블의 경우
                df = pd.DataFrame([], columns=new_header)
                # logger.debug(f"DataFrame 생성: 헤더만 있는 테이블. 컬럼: {new_header}")
            else:
                # 데이터가 있는 경우, 첫 행을 헤더로 설정
                df.columns = new_header
                df = df.iloc[1:].reset_index(drop=True)
                # logger.debug(f"DataFrame 생성: 첫 행을 헤더로 설정. 컬럼: {new_header}")
        else:
            # 헤더 없음 - 기본 컬럼명 사용
            logger.debug(f"DataFrame 생성: 헤더 없음, 기본 컬럼명 사용. 크기: {df.shape}")

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
    # 이전 테이블 하단=797.0, 현재 테이블 상단=50.0 => 페이지 연속된 같은 테이블

    # 케이스 1: 페이지 간 연속성 (기존 로직)
    if curr_page - prev_page == 1:
        # 현재 페이지의 첫 번째 테이블이어야 함
        if curr_pos != 0:
            return False

        # 이전 테이블이 페이지 하단 70% 이후에 있고
        # 현재 테이블이 페이지 상단 30% 이전에 있으면 연속성 높음
        # prev_near_bottom = prev_bottom > (page_height * 0.85)
        # curr_near_top = curr_top < (page_height * 0.15)
        prev_near_bottom = prev_bottom > 740  # 600포인트. 비율말고, 절대값으로 판단해보자.
        curr_near_top = curr_top < 60  # 60포인트. 비율말고, 절대값으로 판단해보자.

        is_continuous = prev_near_bottom and curr_near_top

        # if is_continuous:
        #     logger.debug(f"[페이지간][{prev_page}~{curr_page}] 좌표 기반 연속성 감지: 이전 테이블 하단={prev_bottom:.1f}, 현재 테이블 상단={curr_top:.1f}")
        # else:
        #     logger.debug(f"[페이지간][{prev_page}~{curr_page}] 좌표 기반 연속성 거부: 이전 테이블 하단={prev_bottom:.1f}, 현재 테이블 상단={curr_top:.1f}")

        return is_continuous
    else:
        return False


def merge_continued_tables(prev_table_df: pd.DataFrame, current_table_df: pd.DataFrame) -> pd.DataFrame:
    """
    연결된 테이블을 병합합니다. 컬럼 수가 다른 경우, 요약 행 패턴 등을 감지하여 정렬을 시도합니다.

    Args:
        prev_table_df: 이전 테이블 DataFrame
        current_table_df: 현재 테이블 DataFrame

    Returns:
        pd.DataFrame: 병합된 DataFrame
    """
    if prev_table_df is None:
        return current_table_df

    if current_table_df is None or current_table_df.empty:
        return prev_table_df

    # 헤더만 있는 테이블(empty=True이지만 컬럼은 존재)이거나, 데이터가 있는 테이블을 처리
    # 완전히 비어있는 DataFrame(컬럼도 없음)만 건너뛰도록 수정
    if prev_table_df.empty and prev_table_df.columns.empty:
        return current_table_df

    try:
        # 📋 개선: 작업 시 원본이 아닌 복사본 사용
        prev_df_to_merge = prev_table_df.copy()
        current_df_to_merge = current_table_df.copy()

        prev_col_count = len(prev_df_to_merge.columns)
        curr_col_count = len(current_df_to_merge.columns)

        if prev_col_count != curr_col_count:
            logger.debug(f"테이블 병합: 컬럼 개수가 다름 - 이전:{prev_col_count}, 현재:{curr_col_count}")
            logger.debug(f"이전 테이블:\n{prev_df_to_merge.to_string()}")
            logger.debug(f"현재 테이블:\n{current_df_to_merge.to_string()}")

            # 패턴 1: 현재 테이블이 1개 열이 '적을' 때 (요약 행 케이스)
            if prev_col_count - curr_col_count == 1:
                is_summary_row = False
                if len(current_df_to_merge) == 1:
                    first_val = str(current_df_to_merge.iloc[0, 0]).strip()
                    if any(keyword in first_val for keyword in ["합 계", "합계", "총계", "소계"]):
                        is_summary_row = True

                if is_summary_row:
                    logger.info("요약 행 병합 패턴 감지. 현재 테이블 컬럼 정렬을 시도합니다.")
                    row_values = current_df_to_merge.iloc[0].tolist()
                    new_row_list = [row_values[0]] + [None] + row_values[1:]

                    if len(new_row_list) == prev_col_count:
                        aligned_df = pd.DataFrame([new_row_list], columns=prev_df_to_merge.columns)
                        current_df_to_merge = aligned_df
                        logger.info(f"요약 행 정렬 성공. 병합할 새 데이터:\n{current_df_to_merge.to_string()}")
                    else:
                        logger.warning(f"요약 행 정렬 로직 실패: 생성된 행의 열 개수({len(new_row_list)})가 이전 테이블({prev_col_count})과 불일치.")

            # 패턴 2: 현재 테이블이 1개 열이 '많을' 때 (계층 구조 케이스)
            elif curr_col_count - prev_col_count == 1:
                logger.info("계층적 테이블 병합 패턴 감지. 이전 테이블 컬럼 확장을 시도합니다.")
                # 이전 테이블의 두 번째 위치에 빈 컬럼 삽입
                # 컬럼명은 현재 테이블의 두 번째 컬럼명을 따름 (보통 'Unnamed' 등)
                new_col_name = current_df_to_merge.columns[1]
                prev_df_to_merge.insert(1, new_col_name, None)
                logger.info(f"이전 테이블 확장 성공. 병합할 새 이전 테이블:\n{prev_df_to_merge.to_string()}")

        # 병합 전, 두 DataFrame의 컬럼이 동일한지 마지막으로 확인하고 설정
        if len(prev_df_to_merge.columns) == len(current_df_to_merge.columns):
            # 구조가 정렬되었으므로, 이전 테이블의 컬럼명을 기준으로 현재 테이블의 컬럼명을 강제로 동기화
            current_df_to_merge.columns = prev_df_to_merge.columns
        else:
            logger.warning(f"병합 전 컬럼 수 불일치: 이전({len(prev_df_to_merge.columns)}), 현재({len(current_df_to_merge.columns)}). 병합 결과가 정확하지 않을 수 있습니다.")

        # DataFrame 병합
        merged_df = pd.concat([prev_df_to_merge, current_df_to_merge], ignore_index=True)

        # 메타데이터 보존
        merged_df.attrs = prev_table_df.attrs.copy()

        # logger.debug(f"테이블 병합 완료: 이전 {len(prev_df_to_merge)}행 + 현재 {len(current_df_to_merge)}행 = 총 {len(merged_df)}행")
        # if prev_col_count != curr_col_count:
        #     logger.debug(f"병합된 테이블:\n{merged_df.to_string()}")
        return merged_df

    except Exception as e:
        logger.exception(f"테이블 병합 중 오류: {str(e)}")
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
                # pages_info = table_info.get("merged_from_pages", [table_info.get("page_num")])
                # table_count_merge = table_info.get("table_count_in_group", 1)

                replacement_lines = []
                # if table_count_merge > 1:
                #     replacement_lines.append(f"### 📋 병합된 테이블 (페이지 {pages_info}에서 {table_count_merge}개 병합)")

                # 병합된 테이블의 마크다운 추가
                markdown_lines = table_info["markdown"].strip().split("\n")
                replacement_lines.extend(markdown_lines)

                # 원본 테이블 영역을 병합된 테이블로 교체
                result_lines[start_idx : end_idx + 1] = replacement_lines

                # logger.debug(f"원본 테이블 {original_table_order} → 병합된 테이블 {merged_table_idx} 교체 완료")
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

            # 완전히 비어있는 DataFrame(컬럼도 없음)만 건너뛰고,
            # 헤더만 있는 테이블(empty=True이지만 columns 존재)은 유효한 테이블로 처리
            if table_df is None or (table_df.empty and table_df.columns.empty):
                logger.debug(f"페이지 {page_num} 테이블 {i + 1}: 완전히 비어있는 테이블로 건너뜀")
                continue

            # 헤더만 있는 테이블인지 로깅
            if table_df.empty and not table_df.columns.empty:
                logger.debug(f"페이지 {page_num} 테이블 {i + 1}: 헤더만 있는 테이블로 연속성 판단에 포함 (컬럼: {list(table_df.columns)})")

            # 첫 번째 테이블이거나 이전 그룹이 없으면 새 그룹 시작
            if current_group is None:
                current_group = {"merged_table": table_info, "pages": [page_num], "table_count": 1}
                # logger.debug(f"새로운 테이블 그룹 시작: 페이지 {page_num} 테이블 {i + 1}")
                continue

            # 1차: 좌표 기반 연속성 판단 (우선순위)
            prev_table_info = current_group["merged_table"]
            should_merge = False
            merge_reason = ""

            if is_position_based_continuation(prev_table_info, table_info):
                should_merge = True
                merge_reason = "좌표 기반 연속성"
                # logger.debug(f"테이블 연결 판단[{page_num}]: {merge_reason} 감지")

                # 📋 핵심 개선: 페이지 간 연속성이 확인되면 현재 테이블의 헤더를 첫 행으로 복구
                current_df = table_df.copy()
                if len(current_df.columns) > 0:  # 📋 개선: 헤더만 있는 테이블도 처리 가능
                    # 헤더 추가 전에 원본 테이블 상태 확인
                    was_header_only = current_df.empty

                    # 현재 테이블의 컬럼명을 첫 행으로 삽입
                    header_row = pd.DataFrame([current_df.columns], columns=current_df.columns)
                    current_df = pd.concat([header_row, current_df], ignore_index=True)

                    # if was_header_only:
                    #     logger.debug("페이지 간 연속성 확인: 헤더만 있는 테이블의 헤더를 첫 행으로 복구 완료")
                    # else:
                    #     logger.debug("페이지 간 연속성 확인: 현재 테이블의 헤더를 첫 행으로 복구 완료")

                # 복구된 DataFrame으로 테이블 정보 업데이트
                table_info["dataframe"] = current_df
                table_df = current_df

            if should_merge:
                # 테이블 병합
                prev_table_df = current_group["merged_table"].get("dataframe")
                merged_df = merge_continued_tables(prev_table_df, table_df)

                # 그룹 정보 업데이트
                current_group["merged_table"]["dataframe"] = merged_df
                current_group["merged_table"]["original_dataframe"] = merged_df  # 원본도 업데이트
                current_group["pages"].append(page_num)
                current_group["table_count"] += 1

                # 마크다운은 나중에 단위 변환 후 생성
                # logger.debug(f"✅ 테이블 병합 성공: 페이지 {page_num} 테이블 {i + 1} ({merge_reason}, 총 {len(merged_df)}행)")

            else:
                # 이전 그룹을 완료하고 새 그룹 시작
                grouped_tables.append(current_group)
                current_group = {"merged_table": table_info, "pages": [page_num], "table_count": 1}
                # logger.debug(f"새로운 테이블 그룹 시작: 페이지 {page_num} 테이블 {i + 1}")

    # 마지막 그룹 추가
    if current_group is not None:
        grouped_tables.append(current_group)

    logger.info(f"테이블 그룹화 완료: 총 {len(grouped_tables)}개 그룹, 페이지 범위: {all_page_tables[0]['page_num']}~{all_page_tables[-1]['page_num']}")

    # 결과 포맷팅 및 단위 변환 수행
    result = []
    for i, group in enumerate(grouped_tables):
        group_info = group["merged_table"].copy()
        group_info["merged_from_pages"] = group["pages"]
        group_info["table_count_in_group"] = group["table_count"]
        group_info["table_id"] = i + 1  # 새로운 테이블 ID 할당

        # 병합된 테이블에 대해 단위 변환 수행
        merged_df = group_info.get("dataframe")
        unit_info = group_info.get("unit_info", "")

        if merged_df is not None and not merged_df.empty and unit_info:
            try:
                source_unit_clean = unit_info.replace("단위:", "").replace("단위 :", "").strip().lower()
                target_unit = None

                # 타겟 단위 결정 로직 (구체적인 단위부터 먼저 체크)
                if "조원" in source_unit_clean:
                    target_unit = None  # 이미 최대 단위이므로 변환하지 않음
                elif "십억원" in source_unit_clean:
                    # 십억원일 때도 max 값이 100 이상이면 조원으로 변환
                    max_abs_val = get_max_abs_value_from_dataframe(merged_df)
                    if max_abs_val >= 100:
                        target_unit = "조원"
                    else:
                        target_unit = None  # 변환하지 않음
                elif "억원" in source_unit_clean:
                    # 단순 "억원"인 경우만 처리
                    max_abs_val = get_max_abs_value_from_dataframe(merged_df)
                    if max_abs_val >= 1000:
                        target_unit = "조원"
                    else:
                        target_unit = "십억원"
                elif "백만원" in source_unit_clean:
                    target_unit = "십억원"  # 백만원 -> 십억원
                elif "천원" in source_unit_clean:
                    target_unit = "십억원"  # 천원 -> 십억원
                elif "원" in source_unit_clean and "억" not in source_unit_clean:
                    max_abs_val = get_max_abs_value_from_dataframe(merged_df)
                    if max_abs_val < 100000000:  # 1억 미만이면, 백만원 단위.
                        target_unit = "백만원"
                    else:
                        target_unit = "십억원"  # 원 -> 십억원

                # 단위 변환 실행
                if target_unit and target_unit not in source_unit_clean:
                    converted_df = convert_dataframe_units(merged_df, unit_info, target_unit)
                    if converted_df is not None and not converted_df.empty:
                        group_info["dataframe"] = converted_df
                        group_info["converted_unit"] = converted_df.attrs.get("converted_unit")
                        # logger.debug(f"병합된 테이블 {i + 1} 단위 변환: {unit_info} -> {group_info['converted_unit']}")
                else:
                    logger.debug(f"병합된 테이블 {i + 1} 단위 변환 건너뜀: 타겟 단위({target_unit})가 소스와 동일하거나 없음")

            except Exception as convert_error:
                logger.warning(f"병합된 테이블 {i + 1} 단위 변환 중 오류: {str(convert_error)}")

        # 최종 DataFrame으로 마크다운 생성
        final_df = group_info.get("dataframe")
        if final_df is not None and not final_df.empty:
            group_info["markdown"] = dataframe_to_markdown(final_df, i + 1, "최종데이터")

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

        # logger.debug(f"페이지 {page_num}에서 {len(tables)} 개의 테이블을 발견했습니다 (DataFrame 방식).")

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
                        # 단위 정보 추출
                        unit_info = extract_unit_info(text_above_table)
                        # 원본 텍스트에서 단위 정보 제거
                        text_above_table_content = remove_unit_from_text(text_above_table)
                except Exception as crop_error:
                    logger.debug(f"테이블 {i + 1} 위쪽 텍스트 추출 오류: {str(crop_error)}")

            # 추출된 텍스트를 페이지 콘텐츠에 추가 (단위 정보가 제거된 텍스트)
            if text_above_table_content:
                page_content += text_above_table_content + "\n\n"

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
                                    # logger.debug(f"테이블 {i + 1} 내부에서 단위 정보 발견: '{unit_info}'. 해당 행을 테이블에서 제거합니다.")
                                    # 단위 정보를 포함한 행은 실제 데이터가 아니므로 제거
                                    structured_table = structured_table[1:]
                                    break  # 단위 정보를 찾았으면 반복 중단

                    # 범용적 헤더 처리: 모든 테이블을 헤더가 있는 것으로 가정
                    # 페이지 간 연속성 판단은 analyze_table_structure_across_pages()에서 처리

                    # DataFrame 생성
                    df = create_dataframe_from_table(structured_table, unit_info)

                    # if text_above_table_content:
                    #     page_content += f"{text_above_table_content}\n"

                    # DataFrame을 마크다운으로 변환 (원본 데이터로)
                    if df is not None and not df.empty:
                        markdown_content = dataframe_to_markdown(df, i + 1, "원본데이터")
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

                    # 테이블 정보 저장 (원본 DataFrame만 저장, 단위 변환은 나중에)
                    table_info = {
                        "table_id": i + 1,
                        "page_num": page_num,
                        "dataframe": df,  # 원본 DataFrame 저장
                        "original_dataframe": df,  # 원본 DataFrame도 저장
                        "unit_info": unit_info,
                        "converted_unit": "",  # 변환 전이므로 빈 값
                        "markdown": markdown_content,
                        "raw_data": structured_table,
                        "bbox": table_bbox,  # 좌표 정보 추가
                        "table_position_in_page": i,  # 페이지 내 테이블 순서
                        "page_height": page.height,  # 실제 페이지 높이 추가
                    }

                    result["tables"].append(table_info)

                    # logger.debug(f"테이블 {i + 1} DataFrame 처리 완료: {df.shape if df is not None else 'None'}, 단위: {unit_info} (변환 전)")
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
