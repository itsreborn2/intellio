import time
import logging
from functools import wraps
from typing import Callable, Any
import asyncio
#import psutil

# 로거 설정
logger = logging.getLogger(__name__)

def measure_time(func: Callable) -> Callable:
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
            
            logger.info(
                f"Function: {func.__name__}\n"
                f"Execution time: {execution_time:.2f} seconds\n"
                #f"Memory usage: {memory_used:.2f} MB\n"
                f"Arguments: args={args}, kwargs={kwargs}"
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
        logger.info(f"Function '{func.__name__}' took {execution_time:.2f} seconds to execute")
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper