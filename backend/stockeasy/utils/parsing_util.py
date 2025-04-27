import re


def _clean_numeric_value(str_value: str) -> str:
    """
    숫자 값을 정리하여 숫자만 남기는 함수
    단위(원, 달러 등)와 쉼표 제거
    
    Args:
        str_value: 정리할 문자열 값
        
    Returns:
        정리된 숫자 문자열
    """
    # 단위 제거 (원, 달러 등)
    cleaned_value = re.sub(r'[원달러$£€¥]\s*$', '', str_value)
    # 쉼표 제거
    cleaned_value = cleaned_value.replace(",", "")
    return cleaned_value.strip()

def _process_numeric_value(str_value: str) -> float:
    """
    문자열 값을 숫자로 변환하는 함수
    괄호로 둘러싸인 숫자 확인 (음수 처리)
    단위 제거 및 쉼표 제거 처리
    
    Args:
        str_value: 처리할 문자열 값
        
    Returns:
        변환된 숫자 값
    """
    if not str_value or str_value.strip() == '':
        return None
        
    str_value = str_value.strip()
    
    try:
        # 괄호로 둘러싸인 숫자 확인 (음수 처리)
        if str_value.startswith('(') and str_value.endswith(')'):
            # 괄호 제거 후 단위와 쉼표 제거하고 음수로 변환
            numeric_str = _clean_numeric_value(str_value[1:-1])
            numeric_value = float(numeric_str) * -1
            return numeric_value
        else:
            # 일반 값은 단위와 쉼표 제거
            numeric_str = _clean_numeric_value(str_value)
            return float(numeric_str)
    except (ValueError, TypeError) as e:
        # 변환 실패 시 로그 남기고 None 반환
        print(f"값 변환 실패: {str_value}, 오류: {e}")
        raise

def remove_number_prefix(text:str) -> str:
    """
    항목 이름과 코드에서 숫자 접두사를 제거하고 반환합니다.
    지원하는 패턴:
    - 숫자 접두사 (예: "1.", "1.2.", "1.2.3.")
    - 로마 숫자 접두사 (예: "I.", "II.", "IV.")
    - 기타 유사한 패턴
    """
    if text is None or text.strip() == '':
        return text
    
    # 다양한 숫자 접두사 패턴을 처리하는 정규식
    prefix_patterns = [
        r'^\d+\.\s*',              # "1." 또는 "1. " (공백 있거나 없음)
        r'^\d+\.\d+\.\s*',         # "1.2." 또는 "1.2. " (공백 있거나 없음)
        r'^\d+\.\d+\.\d+\.\s*',    # "1.2.3." 또는 "1.2.3. " (공백 있거나 없음)
        r'^[IVXLCDMivxlcdmⅠ-Ⅻⅰ-ⅻ]+\.\s*', # 모든 로마 숫자 조합 (ASCII 및 유니코드, 혼합 가능)
        r'^\(\d+\)\s*',            # "(1)" 또는 "(1) " (공백 있거나 없음)
        r'^\(\w+\)\s*',            # "(가)" 또는 "(가) " (공백 있거나 없음)
        r'^[a-zA-Z]\.\s*',         # "A." 또는 "A. " (공백 있거나 없음)
        r'^[가-힣]\.\s*',           # "가." 또는 "가. " 등 한글 한 글자와 점 (공백 있거나 없음)
        r'^\d+\)\s*'             # "4)" 또는 "4) " (공백 있거나 없음)
    ]

    removed_prefix = text
    
    for pattern in prefix_patterns:
        removed_prefix = re.sub(pattern, '', removed_prefix)

    return removed_prefix

def remove_number_prefix_toc(text: str) -> str:
    """
    항목 이름과 코드에서 숫자 접두사를 제거하고 반환합니다.
    지원하는 패턴:
    - 숫자 접두사 (예: "1.", "1.2.", "1.2.3.")
    - 로마 숫자 접두사 (예: "I.", "II.", "IV.")
    - 한글 문자 접두사 (예: "가.", "나.")
    - 기타 유사한 패턴
    """
    if text is None or text.strip() == '':
        return text
    
    # 다양한 숫자 접두사 패턴을 처리하는 정규식 (공백 없이도 동작하도록)
    prefix_patterns = [
        r'^\d+\.',                 # "1."
        r'^\d+\.\d+\.',            # "1.2."
        r'^\d+\.\d+\.\d+\.',       # "1.2.3."
        r'^[IVXLCDMivxlcdm]+\.',    # 로마 숫자 "I.", "II.", "IV." 등
        r'^\(\d+\)',               # "(1)"
        r'^\(\w+\)',               # "(가)" 등
        r'^[a-zA-Z]\.',            # "A.", "a." 등
        r'^[가-힣]\.',              # "가.", "나." 등 한글 한 글자와 점
    ]

    removed_prefix = text.replace(" ", "") # 모든 공백제거
    
    for pattern in prefix_patterns:
        removed_prefix = re.sub(pattern, '', removed_prefix)
        # 제거 후 앞에 공백이 있으면 제거
        removed_prefix = removed_prefix.lstrip()

    # 문자열 끝에 오는 괄호와 그 내용을 제거 (문자열 끝에 있는 경우에만)
    removed_prefix = re.sub(r'\([^)]*\)$', '', removed_prefix)

    return removed_prefix

def remove_comment_number(text: str) -> str:
    """
    항목 이름과 코드에서 <주석 숫자> 패턴을 제거하고 반환합니다.
    """
    if text is None or text.strip() == '':
        return text
    
    s_text = text
    s_text = re.sub(r'\s*\(주[\d,]+\)\s*', '',s_text).strip()
    s_text = re.sub(r'<주석\s*\d+>', '', s_text).strip() # <주석 숫자> 패턴 제거
    return s_text

