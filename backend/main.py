import uvicorn
from common.app import app                              # 공통 FastAPI 앱 가져오기
from common.api.v1 import api_router_common
from common.core.config import settings
from doceasy.api.v1 import api_router_doceasy         # 닥이지 서비스 라우터 가져오기
from stockeasy.api.v1 import api_router_stockeasy         # 스탁이지 서비스 라우터 가져오기
import logging
from loguru import logger
from datetime import datetime
import pytz
import sys
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import time

# 서울 타임존 설정
seoul_tz = pytz.timezone('Asia/Seoul')

class SeoulFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, seoul_tz)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.isoformat()

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 핸들러에 포맷터 설정
for handler in logging.getLogger().handlers:
    handler.setFormatter(SeoulFormatter())

# loguru 로거 설정 수정
# 모든 기존 핸들러 제거
logger.remove()

# 새 핸들러 추가 - INFO 레벨 이상 로그 출력
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    enqueue=True
)

# 디버그 로그를 파일에 저장 (선택 사항)
logger.add(
    "logs/debug_{time}.log",
    rotation="50 MB",
    retention="10 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    enqueue=True
)

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
