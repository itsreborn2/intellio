import json
import re
import time
import logging
from functools import wraps
from typing import Callable, Any, TypeVar, Union, Optional
import asyncio
import pandas as pd

# 로거 설정
logger = logging.getLogger(__name__)

def remove_null_chars(obj):
    """
    JSON 객체에서 NULL 문자(\u0000)를 제거합니다.
    
    Args:
        obj: 문자열, 딕셔너리, 리스트 등 JSON으로 변환될 수 있는 객체
        
    Returns:
        NULL 문자가 제거된 객체
    """
    if isinstance(obj, str):
        return obj.replace('\u0000', '')
    elif isinstance(obj, dict):
        return {k: remove_null_chars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [remove_null_chars(item) for item in obj]
    else:
        return obj
    
def extract_json_from_text(text: str) -> str:
    """
    텍스트에서 JSON 부분을 추출합니다.
    
    Args:
        text: 텍스트
        
    Returns:
        JSON 텍스트
    """
    # JSON 시작과 끝 찾기
    json_patterns = [
        r"```json\s*([\s\S]*?)\s*```",  # ```json ... ``` 형식
        r"```\s*([\s\S]*?)\s*```",      # ``` ... ``` 형식
        r"\{[\s\S]*\}"                   # { ... } 형식
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # 가장 긴 매치를 반환 (완전한 JSON 객체일 가능성이 높음)
            return max(matches, key=len)
    
    # JSON 패턴을 찾지 못한 경우 전체 텍스트가 JSON인지 확인
    if text.strip().startswith("{") and text.strip().endswith("}"):
        return text
        
    return "" 

def remove_json_block(content:str):
    # 전체 문자열이 코드 블록으로 감싸진 경우
    content = re.sub(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', r'\1', content, flags=re.DOTALL)
    # 시작 부분에 ```json이 있는 경우
    content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.DOTALL)
    # 끝 부분에 ``` 가 있는 경우
    content = re.sub(r'\n?```\s*$', '', content, flags=re.DOTALL)
    # 문자열 앞뒤 공백 제거
    content = content.strip()
    return content

def measure_time_async(func: Callable) -> Callable:
    """
    함수의 실행 시간을 측정하고 로깅하는 데코레이터
    
    Args:
        func: 측정할 함수
    
    Returns:
        wrapper: 실행 시간을 측정하는 래퍼 함수
    """
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        #print(f"measure_time")
        #start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        try:
            result = await func(*args, **kwargs)
            end_time = time.time()
            #end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            execution_time = end_time - start_time
            #memory_used = end_memory - start_memory
            
            logger.warn(
                f"함수 실행시간 : {func.__name__} : {execution_time:.2f} sec\n"
                #f"Memory usage: {memory_used:.2f} MB\n"
                #f"Arguments: args={args}, kwargs={kwargs}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            raise

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logger.warn(f"함수 실행시간 : {func.__name__} : {execution_time:.2f} sec")
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


#T = TypeVar('T')

def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """비동기 함수에 대한 재시도 데코레이터

    Args:
        retries (int): 최대 재시도 횟수
        delay (float): 초기 대기 시간(초)
        backoff_factor (float): 대기 시간 증가 계수
        exceptions (tuple): 재시도할 예외 목록

    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            wait_time = delay

            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        logger.error(
                            f"함수 {func.__name__} 실행 실패 (최대 재시도 횟수 초과)\n"
                            f"에러: {str(e)}\n"
                            f"Args: {args}\n"
                            f"Kwargs: {kwargs}",
                            exc_info=True
                        )
                        raise
                    
                    logger.warning(
                        f"함수 {func.__name__} 실행 실패 (시도 {attempt + 1}/{retries + 1})\n"
                        f"에러: {str(e)}\n"
                        f"대기 시간: {wait_time}초"
                    )
                    
                    await asyncio.sleep(wait_time)
                    wait_time *= backoff_factor
            
            raise last_exception
        return wrapper
    return decorator

def dict_to_formatted_str(data: dict, sort_keys: bool = False) -> str:
    """딕셔너리를 보기 좋게 들여쓰기와 줄바꿈이 적용된 문자열로 변환합니다.
    """
    json_string = json.dumps(data, indent=4, ensure_ascii=False, sort_keys=sort_keys)
    return json_string


# ========================================
# 안전한 타입 변환 유틸리티 함수들
# ========================================

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    값을 안전하게 float로 변환합니다.
    
    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값
        
    Returns:
        변환된 float 값 또는 기본값
    """
    if value is None or value == '' or value == 'null':
        return default
    
    # pandas의 NaN 체크
    if pd.isna(value):
        return default
    
    # 문자열에서 nan 체크
    if isinstance(value, str) and value.lower() in ['nan', 'none', 'null']:
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    값을 안전하게 int로 변환합니다.
    
    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값
        
    Returns:
        변환된 int 값 또는 기본값
    """
    if value is None or value == '' or value == 'null':
        return default
    
    # pandas의 NaN 체크
    if pd.isna(value):
        return default
    
    # 문자열에서 nan 체크
    if isinstance(value, str) and value.lower() in ['nan', 'none', 'null']:
        return default
    
    try:
        # float로 먼저 변환 후 int로 (소수점이 있는 문자열 처리)
        return int(float(value))
    except (ValueError, TypeError, OverflowError):
        return default


def safe_price_float(value: Any, default: float = 0.0) -> float:
    """
    가격 데이터를 안전하게 float로 변환합니다. (safe_float의 별칭)
    
    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값
        
    Returns:
        변환된 float 값 또는 기본값
    """
    return safe_float(value, default)


def safe_str(value: Any, default: str = "") -> str:
    """
    값을 안전하게 str로 변환합니다.
    
    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값
        
    Returns:
        변환된 str 값 또는 기본값
    """
    if value is None:
        return default
    
    # pandas의 NaN 체크
    if pd.isna(value):
        return default
    
    try:
        return str(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """
    값을 안전하게 bool로 변환합니다.
    
    Args:
        value: 변환할 값
        default: 변환 실패 시 기본값
        
    Returns:
        변환된 bool 값 또는 기본값
    """
    if value is None:
        return default
    
    # pandas의 NaN 체크
    if pd.isna(value):
        return default
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes', 'on', 'y']
    
    try:
        return bool(value)
    except (ValueError, TypeError):
        return default


def safe_float_or_none(value: Any) -> Optional[float]:
    """
    값을 안전하게 float로 변환하거나 None을 반환합니다.
    
    Args:
        value: 변환할 값
        
    Returns:
        변환된 float 값 또는 None
    """
    if value is None or value == '' or value == 'null':
        return None
    
    # pandas의 NaN 체크
    if pd.isna(value):
        return None
    
    # 문자열에서 nan 체크
    if isinstance(value, str) and value.lower() in ['nan', 'none', 'null']:
        return None
    
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return None


def safe_int_or_none(value: Any) -> Optional[int]:
    """
    값을 안전하게 int로 변환하거나 None을 반환합니다.
    
    Args:
        value: 변환할 값
        
    Returns:
        변환된 int 값 또는 None
    """
    if value is None or value == '' or value == 'null':
        return None
    
    # pandas의 NaN 체크
    if pd.isna(value):
        return None
    
    # 문자열에서 nan 체크
    if isinstance(value, str) and value.lower() in ['nan', 'none', 'null']:
        return None
    
    try:
        # float로 먼저 변환 후 int로 (소수점이 있는 문자열 처리)
        return int(float(value))
    except (ValueError, TypeError, OverflowError):
        return None


def safe_series_to_list(series: Any, default_list: Optional[list] = None) -> list:
    """
    pandas Series를 안전하게 리스트로 변환합니다.
    
    Args:
        series: 변환할 Series 또는 기타 iterable
        default_list: 변환 실패 시 기본값
        
    Returns:
        변환된 리스트 또는 기본값
    """
    if default_list is None:
        default_list = []
    
    if series is None:
        return default_list
    
    try:
        if hasattr(series, 'empty') and series.empty:
            return default_list
        
        # pandas Series인 경우
        if hasattr(series, 'tolist'):
            return [safe_float(x) if not pd.isna(x) else None for x in series.tolist()]
        
        # 일반 iterable인 경우
        if hasattr(series, '__iter__'):
            return [safe_float(x) if x is not None and not pd.isna(x) else None for x in series]
        
        return default_list
        
    except Exception:
        return default_list

