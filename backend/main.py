import uvicorn
from common.app import app                              # 공통 FastAPI 앱 가져오기
from common.api.v1 import api_router_common
from common.core.config import settings
from doceasy.api.v1 import api_router_doceasy         # 닥이지 서비스 라우터 가져오기
from stockeasy.api.v1 import api_router_stockeasy         # 스탁이지 서비스 라우터 가져오기
from loguru import logger # 추가
from datetime import datetime
import pytz # Formatter 등에서 사용될 수 있으므로 유지 (실제 사용처 확인 필요)
import sys # loguru 설정을 위해 추가
import logging # InterceptHandler를 위해 추가
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import time

# --- common.core.logger.py에서 가져온 로깅 설정 ---

# InterceptHandler 클래스 정의
class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        depth_val = 0
        frame = logging.currentframe()
        # 루프를 통해 올바른 스택 깊이 계산
        # logging 모듈 자체 또는 이 InterceptHandler 파일 외부의 프레임을 찾을 때까지 반복
        while frame and (frame.f_code.co_filename == logging.__file__ or frame.f_code.co_filename == __file__):
            frame = frame.f_back
            depth_val += 1
        if frame is None: # 프레임을 찾지 못한 경우 (예: 인터랙티브 세션)
            depth_val = 0
            
        logger.opt(depth=depth_val, exception=record.exc_info).log(
            level, record.getMessage()
        )

# filter_log 함수 정의
def filter_log(record):
    name = record["name"]
    levelno = record["level"].no

    if name.startswith("httpx") and levelno < logger.level("WARNING").no:
        return False
    if name.startswith("httpcore") and levelno < logger.level("WARNING").no:
        return False
    if name.startswith("openai") and levelno < logger.level("WARNING").no:
        return False
    if name.startswith("langchain.retrievers.multi_query") and levelno < logger.level("WARNING").no:
        return False
    if name.startswith("pdfminer") and levelno < logger.level("ERROR").no: # pdfminer는 ERROR 이상만
        return False
    return True

# Loguru 로거 설정
logger.remove()  # 모든 기존 핸들러 제거

# 포맷 정의 (common.core.logger.py의 STDOUT_FORMAT, FILE_FORMAT 참고)
STDOUT_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"


# 1. 콘솔 핸들러 (stdout)
logger.add(
    sys.stdout,
    format=STDOUT_FORMAT,
    level=settings.LOG_LEVEL.upper() if hasattr(settings, 'LOG_LEVEL') else "INFO", # settings에 LOG_LEVEL이 있으면 사용
    filter=filter_log,
    colorize=True,
)

# 2. 디버그 파일 핸들러
# 로그 파일 경로 설정 (settings에 LOG_PATH가 있다면 사용)
log_file_path = Path(settings.LOG_PATH if hasattr(settings, 'LOG_PATH') else "logs") / "debug_{time}.log"
if not log_file_path.parent.exists():
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

logger.add(
    log_file_path,
    rotation="30 MB", # settings.LOG_ROTATION_SIZE 등 사용 가능
    retention="10 days", # settings.LOG_RETENTION 등 사용 가능
    format=FILE_FORMAT,
    level="DEBUG", # 디버그 파일은 DEBUG 레벨 고정 또는 settings.LOG_FILE_LEVEL 등 사용
    filter=filter_log,
    enqueue=True
)
    
# 표준 로깅 시스템을 Loguru로 리다이렉션
# 기본 로깅 설정은 모든 로거에 영향을 미치므로 level=0 또는 가장 낮은 레벨로 설정
# force=True는 기존 핸들러를 제거하고 새로 설정합니다.
logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG if settings.ENV == "development" else logging.INFO, force=True)

# uvicorn 등 특정 표준 로거의 로그가 loguru를 통해 처리되도록 핸들러 명시적 설정 및 전파 방지
std_loggers_to_intercept = ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]
for logger_name in std_loggers_to_intercept:
    std_logger = logging.getLogger(logger_name)
    std_logger.handlers = [InterceptHandler()]
    std_logger.propagate = False # Loguru로만 출력되도록 중복 로깅 방지

logger.info("Loguru 로깅 시스템이 main.py에서 성공적으로 초기화되었습니다.")
# --- 로깅 설정 종료 ---


# 애플리케이션 시작 시 로깅 초기화
# initialize_logging() # 삭제됨

logger.info(f"시작 : {settings.API_V1_STR}")

# API 라우터 등록
app.include_router(api_router_common, prefix=settings.API_V1_STR) # Common api router 등록

# 닥이지 서비스 라우터 포함
app.include_router(api_router_doceasy, prefix=settings.API_V1_STR)

# 스탁이지 라우터
app.include_router(api_router_stockeasy, prefix=settings.API_V1_STR)


# 정적 파일 서빙 설정 (임시 파일용)
TEMP_DIR = settings.TEMP_DIR
temp_path = Path(TEMP_DIR)
if not temp_path.exists():
    temp_path.mkdir(parents=True, exist_ok=True)

app.mount("/download_chat_session", StaticFiles(directory=TEMP_DIR), name="download_chat_session")

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)          # 포트 8000에서 서버 실행

# 파일 변경 감지 테스트를 위한 주석 추가
# 두 번째 테스트 주석 추가
