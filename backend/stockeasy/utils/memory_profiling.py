"""메모리 프로파일링 데코레이터"""

import functools
import tracemalloc
import asyncio
import psutil
import os
from loguru import logger
from typing import Any, Callable


def memory_profile_async(threshold_mb: float = 10.0):
    """비동기 함수용 메모리 프로파일링 데코레이터
    
    Args:
        threshold_mb: 로깅할 메모리 증가 임계값 (MB)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # tracemalloc 시작 (이미 시작되었으면 무시)
            if not tracemalloc.is_tracing():
                tracemalloc.start(10)
                
            # 시작 시점 메모리
            process = psutil.Process(os.getpid())
            start_memory = process.memory_info().rss / (1024 * 1024)  # MB
            
            # 메모리 스냅샷
            snapshot_start = tracemalloc.take_snapshot()
            
            # 함수명 추출
            if hasattr(func, '__qualname__'):
                func_name = func.__qualname__
            else:
                func_name = func.__name__
            
            try:
                # 실제 함수 실행
                result = await func(*args, **kwargs)
                
                # 종료 시점 메모리
                end_memory = process.memory_info().rss / (1024 * 1024)  # MB
                memory_diff = end_memory - start_memory
                
                # 메모리 스냅샷 비교
                snapshot_end = tracemalloc.take_snapshot()
                top_stats = snapshot_end.compare_to(snapshot_start, 'lineno')
                
                # 임계값 이상 증가했으면 로깅
                if abs(memory_diff) > threshold_mb:
                    logger.warning(f"[메모리프로파일] {func_name} - 메모리 변화: {memory_diff:+.1f}MB (시작: {start_memory:.1f}MB → 종료: {end_memory:.1f}MB)")
                    
                    # 상위 5개 메모리 증가 위치
                    logger.warning(f"[메모리프로파일] {func_name} - 상위 메모리 증가 위치:")
                    for i, stat in enumerate(top_stats[:5]):
                        if stat.size_diff > 1024 * 1024:  # 1MB 이상
                            logger.warning(f"  #{i+1}: {stat.filename}:{stat.lineno} +{stat.size_diff / 1024 / 1024:.1f}MB")
                
                return result
                
            except Exception as e:
                # 오류 시에도 메모리 정보 로깅
                end_memory = process.memory_info().rss / (1024 * 1024)
                memory_diff = end_memory - start_memory
                logger.error(f"[메모리프로파일] {func_name} - 오류 발생, 메모리 변화: {memory_diff:+.1f}MB")
                raise
                
        return wrapper
    return decorator


def track_agent_memory(agent_name: str):
    """에이전트별 메모리 추적 데코레이터
    
    Args:
        agent_name: 에이전트 이름
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, state: dict) -> dict:
            # 시작 시점 상태 크기
            import sys
            state_size_start = sys.getsizeof(str(state)) / 1024  # KB
            
            # 실제 함수 실행
            result = await func(self, state)
            
            # 종료 시점 상태 크기
            state_size_end = sys.getsizeof(str(result)) / 1024  # KB
            state_size_diff = state_size_end - state_size_start
            
            # 상태 크기가 1MB 이상 증가했으면 경고
            if state_size_diff > 1024:  # 1MB = 1024KB
                logger.warning(f"[에이전트메모리] {agent_name} - 상태 크기 증가: {state_size_diff/1024:.1f}MB (시작: {state_size_start/1024:.1f}MB → 종료: {state_size_end/1024:.1f}MB)")
                
                # 어떤 키가 크게 증가했는지 확인
                if isinstance(result, dict):
                    key_sizes = {}
                    for key, value in result.items():
                        try:
                            key_size = sys.getsizeof(str(value)) / 1024 / 1024  # MB
                            if key_size > 1:  # 1MB 이상
                                key_sizes[key] = key_size
                        except:
                            pass
                    
                    if key_sizes:
                        sorted_keys = sorted(key_sizes.items(), key=lambda x: x[1], reverse=True)
                        logger.warning(f"[에이전트메모리] {agent_name} - 큰 키들: {sorted_keys[:5]}")
            
            return result
            
        return wrapper
    return decorator 