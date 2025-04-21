import json
import time
import logging
from functools import wraps
from typing import Callable, Any, TypeVar
import asyncio

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
        print(f"measure_time")
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
        logger.warn(f"함수 실행시간 : {func.__name__} : {execution_time:.2f} sec\n")
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

