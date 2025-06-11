"""
증권 데이터 수집 서비스 로깅 설정 (Loguru 기반)
"""
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from loguru import logger
from stockeasy.collector.core.config import get_settings


def setup_loguru() -> None:
    """Loguru 로거 설정"""
    settings = get_settings()
    
    # 기본 로거 제거 (loguru의 기본 stderr 핸들러)
    logger.remove()
    
    # 로그 디렉토리 설정
    if settings.ENV == "development":
        log_dir = Path("./logs")
    else:
        # 프로덕션 환경에서는 여러 경로 순서대로 시도
        log_paths = [
            Path("/backend/stockeasy/collector/logs"),  # Docker 볼륨 마운트 경로
            Path("./logs")
        ]
        
        log_dir = None
        for path in log_paths:
            try:
                path.mkdir(parents=True, exist_ok=True)
                # 테스트 파일 생성해서 권한 확인
                test_file = path / "test_write.tmp"
                test_file.write_text("test")
                test_file.unlink()
                log_dir = path
                break
            except (PermissionError, OSError) as e:
                print(f"로그 경로 {path} 사용 불가: {e}")
                continue
        
        if log_dir is None:
            # 모든 경로가 실패하면 /tmp 사용 (강제)
            log_dir = Path("/tmp/stockeasy_logs")
            print(f"모든 로그 경로 실패, fallback 경로 사용: {log_dir}")
    
    # 최종 로그 디렉토리 생성 및 권한 확인
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        # 최종 권한 테스트
        test_file = log_dir / "final_test.tmp"
        test_file.write_text("final test")
        test_file.unlink()
        print(f"로그 디렉토리 설정 완료: {log_dir}")
    except Exception as e:
        print(f"로그 디렉토리 생성 실패: {log_dir}, 오류: {e}")
        # 최후의 수단: 시스템 임시 디렉토리 사용
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "stockeasy_collector_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        print(f"임시 로그 디렉토리 사용: {log_dir}")
    
    # 로그 레벨 설정
    log_level = settings.LOG_LEVEL.upper()
    
    # 콘솔 로거 (컬러풀한 출력)
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # 파일 로거 (일반 로그)
    logger.add(
        log_dir / "collector_{time:YYYY-MM-DD}.log",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message}",
        rotation="00:00",  # 매일 자정에 로테이션
        retention="30 days",  # 30일 보관
        compression="gz",  # gzip 압축
        encoding="utf-8",
        enqueue=True  # 멀티프로세싱 환경에서 안전
    )
    
    # 에러 로거 (에러만 별도 파일)
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} | {message} | {exception}",
        rotation="00:00",
        retention="90 days",  # 에러는 90일 보관
        compression="gz",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
    
    # JSON 로거 (구조화된 로그 - 모니터링용)
    if settings.ENV == "production":
        logger.add(
            log_dir / "collector_json_{time:YYYY-MM-DD}.log",
            level="INFO",
            format="{message}",
            rotation="00:00",
            retention="7 days",
            compression="gz",
            encoding="utf-8",
            enqueue=True,
            serialize=True  # JSON 형태로 출력
        )
    
    # uvicorn 기본 로깅은 그대로 두고 loguru와 공존
    # (uvicorn access log를 건드리지 않음)
    
    # 성공적으로 설정되었음을 로그
    logger.info("Loguru 로깅 시스템 초기화 완료")
    logger.info(f"로그 레벨: {log_level}")
    logger.info(f"로그 디렉토리: {log_dir}")


def get_logger(name: str = None) -> "loguru.Logger":
    """
    로거 인스턴스 반환
    
    Args:
        name (str, optional): 로거 이름. None인 경우 기본 loguru 로거 반환
    
    Returns:
        loguru.Logger: 로거 인스턴스
    """
    if name:
        return logger.bind(name=name)
    return logger


class LoggerMixin:
    """로거 믹스인 클래스 (Loguru 버전)"""
    
    @property
    def logger(self) -> "loguru.Logger":
        """클래스별 로거 반환"""
        class_name = self.__class__.__name__
        return logger.bind(name=class_name)


class LogContext:
    """로그 컨텍스트 관리자 (Loguru 버전)"""
    
    def __init__(self, logger_instance: "loguru.Logger", operation: str, **kwargs):
        self.logger = logger_instance
        self.operation = operation
        self.context = kwargs
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"[{self.operation}] 시작", extra=self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = datetime.now() - self.start_time
        
        if exc_type is None:
            self.logger.info(
                f"[{self.operation}] 완료 (소요시간: {duration.total_seconds():.2f}초)",
                extra=self.context
            )
        else:
            self.logger.error(
                f"[{self.operation}] 실패 (소요시간: {duration.total_seconds():.2f}초): {exc_val}",
                extra=self.context
            )
    
    def log_progress(self, message: str, **kwargs):
        """진행 상황 로깅"""
        context = {**self.context, **kwargs}
        self.logger.info(f"[{self.operation}] {message}", extra=context)


def log_api_call(api_name: str, symbol: str = None, **kwargs):
    """API 호출 로깅 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **func_kwargs):
            start_time = datetime.now()
            
            # 로그 컨텍스트 생성
            context = {
                "api_name": api_name,
                "symbol": symbol or func_kwargs.get("symbol", "unknown"),
                **kwargs
            }
            
            logger.info(f"API 호출 시작: {api_name}", extra=context)
            
            try:
                result = await func(*args, **func_kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.info(
                    f"API 호출 성공: {api_name} (소요시간: {duration:.2f}초)",
                    extra={**context, "duration": duration, "success": True}
                )
                return result
                
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.error(
                    f"API 호출 실패: {api_name} (소요시간: {duration:.2f}초): {e}",
                    extra={**context, "duration": duration, "success": False, "error": str(e)}
                )
                raise
        
        return wrapper
    return decorator


def log_scheduler_job(job_name: str):
    """스케줄러 작업 로깅 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.now()
            
            logger.info(f"스케줄 작업 시작: {job_name}")
            
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.success(
                    f"스케줄 작업 완료: {job_name} (소요시간: {duration:.2f}초)",
                    extra={"job_name": job_name, "duration": duration, "success": True}
                )
                return result
                
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.error(
                    f"스케줄 작업 실패: {job_name} (소요시간: {duration:.2f}초): {e}",
                    extra={"job_name": job_name, "duration": duration, "success": False, "error": str(e)}
                )
                raise
        
        return wrapper
    return decorator


# 전역 로거 인스턴스들 (하위 호환성을 위해)
def get_collector_logger():
    """데이터 수집 전용 로거"""
    return get_logger("collector")

def get_api_logger():
    """API 전용 로거"""
    return get_logger("api")

def get_cache_logger():
    """캐시 전용 로거"""
    return get_logger("cache")

def get_websocket_logger():
    """WebSocket 전용 로거"""
    return get_logger("websocket")


# 애플리케이션 시작 시 자동으로 설정
try:
    setup_loguru()
except Exception as e:
    # fallback to print if logger setup fails
    print(f"로거 설정 실패: {e}")
    print("기본 콘솔 로거로 fallback 합니다.")
    # 최소한의 콘솔 로거라도 설정
    try:
        logger.remove()
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            colorize=True
        )
        print("기본 콘솔 로거 설정 완료")
    except Exception as fallback_error:
        print(f"기본 로거 설정도 실패: {fallback_error}")
        # 이 경우에는 print만 사용