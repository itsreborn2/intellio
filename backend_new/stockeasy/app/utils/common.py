import time
import logging
from functools import wraps
from typing import Callable, Any
import asyncio

# 로거 설정
logger = logging.getLogger(__name__)

def measure_time_async(func: Callable) -> Callable:
    """
    비동기 함수의 실행 시간을 측정하고 로깅하는 데코레이터
    
    Args:
        func: 측정할 비동기 함수
    
    Returns:
        wrapper: 실행 시간을 측정하는 래퍼 함수
    
    Example:
        @measure_time_async
        async def my_async_function():
            await some_async_operation()
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # 함수 이름과 시작 시간 기록
        func_name = func.__name__
        start_time = time.time()
        
        try:
            # 비동기 함수 실행
            result = await func(*args, **kwargs)
            
            # 실행 시간 계산 및 로깅
            execution_time = time.time() - start_time
            logger.info(
                f"Function '{func_name}' completed in {execution_time:.2f} seconds"
            )
            
            return result
            
        except Exception as e:
            # 에러 발생 시 실행 시간과 함께 에러 로깅
            execution_time = time.time() - start_time
            logger.error(
                f"Function '{func_name}' failed after {execution_time:.2f} seconds. Error: {str(e)}"
            )
            raise
    
    return wrapper
